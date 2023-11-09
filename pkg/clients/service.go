package clients

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"

	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/canonical/identity-platform-admin-ui/internal/monitoring"
	hClient "github.com/ory/hydra-client-go/v2"
	"go.opentelemetry.io/otel/trace"
)

type PaginationLinksMeta struct {
	First PaginationMeta `json:"first,omitempty"`
	Last  PaginationMeta `json:"last,omitempty"`
	Prev  PaginationMeta `json:"prev,omitempty"`
	Next  PaginationMeta `json:"next,omitempty"`
}

type PaginationMeta struct {
	Page string `json:"page,omitempty"`
	Size int    `json:"size,omitempty"`
}

type ListClientsRequest struct {
	PaginationMeta
	Owner      string `json:"owner,omitempty"`
	ClientName string `json:"client_name,omitempty"`
}

type ErrorOAuth2 struct {
	Error            string `json:"error,omitempty"`
	ErrorDescription string `json:"error_description,omitempty"`
	StatusCode       int    `json:"-"`
}

type ServiceResponse struct {
	Links        *PaginationLinksMeta
	ServiceError *ErrorOAuth2
	Resp         interface{}
	Meta         map[string]string
}

type Service struct {
	hydra HydraClientInterface

	linksRegex *regexp.Regexp

	tracer  trace.Tracer
	monitor monitoring.MonitorInterface
	logger  logging.LoggerInterface
}

func (s *Service) GetClient(ctx context.Context, clientID string) (*ServiceResponse, error) {
	ctx, span := s.tracer.Start(ctx, "hydra.OAuth2Api.GetOAuth2Client")
	defer span.End()

	ret := NewServiceResponse()

	c, resp, err := s.hydra.OAuth2Api().
		GetOAuth2Client(ctx, clientID).
		Execute()

	if err != nil {
		se, err := s.parseServiceError(resp)
		if err != nil {
			return nil, err
		}
		ret.ServiceError = se
	}
	ret.Resp = c
	return ret, nil
}

func (s *Service) DeleteClient(ctx context.Context, clientID string) (*ServiceResponse, error) {
	ctx, span := s.tracer.Start(ctx, "hydra.OAuth2Api.DeleteOAuth2Client")
	defer span.End()

	ret := NewServiceResponse()

	resp, err := s.hydra.OAuth2Api().
		DeleteOAuth2Client(ctx, clientID).
		Execute()

	if err != nil {
		se, err := s.parseServiceError(resp)
		if err != nil {
			return nil, err
		}
		ret.ServiceError = se
	}
	return ret, nil
}

func (s *Service) CreateClient(ctx context.Context, client *hClient.OAuth2Client) (*ServiceResponse, error) {
	ctx, span := s.tracer.Start(ctx, "hydra.OAuth2Api.CreateOAuth2Client")
	defer span.End()

	ret := NewServiceResponse()

	c, resp, err := s.hydra.OAuth2Api().
		CreateOAuth2Client(ctx).
		OAuth2Client(*client).
		Execute()

	if err != nil {
		se, err := s.parseServiceError(resp)
		if err != nil {
			return nil, err
		}
		ret.ServiceError = se
	}
	ret.Resp = c
	return ret, nil
}

func (s *Service) UpdateClient(ctx context.Context, client *hClient.OAuth2Client) (*ServiceResponse, error) {
	ctx, span := s.tracer.Start(ctx, "hydra.OAuth2Api.SetOAuth2Client")
	defer span.End()

	ret := NewServiceResponse()

	c, resp, err := s.hydra.OAuth2Api().
		SetOAuth2Client(ctx, *client.ClientId).
		OAuth2Client(*client).
		Execute()

	if err != nil {
		se, err := s.parseServiceError(resp)
		if err != nil {
			return nil, err
		}
		ret.ServiceError = se
	}
	ret.Resp = c
	return ret, nil
}

func (s *Service) ListClients(ctx context.Context, cs *ListClientsRequest) (*ServiceResponse, error) {
	ctx, span := s.tracer.Start(ctx, "hydra.OAuth2Api.ListOAuth2Clients")
	defer span.End()

	ret := NewServiceResponse()

	c, resp, err := s.hydra.OAuth2Api().ListOAuth2Clients(ctx).
		ClientName(cs.ClientName).
		Owner(cs.Owner).
		PageSize(int64(cs.Size)).
		PageToken(cs.Page).
		Execute()

	if err != nil {
		se, err := s.parseServiceError(resp)
		if err != nil {
			return nil, err
		}
		ret.ServiceError = se
	}
	ret.Resp = c

	l := resp.Header.Get("Link")
	if l != "" {
		ret.Links = s.parseLinks(l)
	}

	ret.Meta["total_count"] = resp.Header.Get("X-Total-Count")

	return ret, nil
}
func (s *Service) UnmarshalClient(data []byte) (*hClient.OAuth2Client, error) {
	c := hClient.NewOAuth2Client()
	err := json.Unmarshal(data, c)
	if err != nil {
		return nil, err
	}
	return c, nil
}

func (s *Service) parseLinks(ls string) *PaginationLinksMeta {
	p := new(PaginationLinksMeta)
	links := s.linksRegex.FindAllStringSubmatch(ls, -1)
	for _, link := range links {
		l := link[1]
		t := link[2]
		if l == "" {
			continue
		}

		parsedURL, err := url.Parse(l)
		if err != nil {
			s.logger.Errorf("Failed to parse: %s, not a URL: %s", l, err)
			continue
		}
		q := parsedURL.Query()
		size, _ := strconv.Atoi(q["page_size"][0])
		if err != nil {
			s.logger.Errorf("Failed to parse: %s, not an int", err)
			continue
		}

		switch t {
		case "first":
			p.First = PaginationMeta{q["page_token"][0], size}
		case "last":
			p.Last = PaginationMeta{q["page_token"][0], size}
		case "prev":
			p.Prev = PaginationMeta{q["page_token"][0], size}
		case "next":
			p.Next = PaginationMeta{q["page_token"][0], size}
		default:
			// We should never end up here
			s.logger.Warn("Unexpected Links header format: ", ls)
		}
	}
	return p
}

func (s *Service) parseServiceError(r *http.Response) (*ErrorOAuth2, error) {
	// The hydra client does not return any errors, we need to parse the response body and create our
	// own objects.
	// Should we use our objects instead of reusing the ones from the sdk?
	se := new(ErrorOAuth2)

	if r == nil {
		s.logger.Debugf("Got no response from hydra service")
		se.Error = "internal_server_error"
		se.ErrorDescription = "Failed to call hydra service"
		se.StatusCode = http.StatusInternalServerError
		return se, nil
	}

	json_data, err := io.ReadAll(r.Body)
	if err != nil {
		s.logger.Debugf("Failed to read response body: %s", err)
		return se, err
	}
	err = json.Unmarshal(json_data, se)
	if err != nil {
		s.logger.Debugf("Failed to unmarshal JSON: %s", err)
		return se, err
	}
	se.StatusCode = r.StatusCode

	return se, nil
}

func NewService(hydra HydraClientInterface, tracer trace.Tracer, monitor monitoring.MonitorInterface, logger logging.LoggerInterface) *Service {
	s := new(Service)

	s.linksRegex = regexp.MustCompile(`<(?P<link>[^>]*)>; rel="(?P<type>\w*)"`)
	s.hydra = hydra

	s.monitor = monitor
	s.tracer = tracer
	s.logger = logger

	return s
}

func NewServiceResponse() *ServiceResponse {
	sr := new(ServiceResponse)
	sr.Meta = make(map[string]string)
	return sr
}

func NewListClientsRequest(cn, owner, page string, size int) *ListClientsRequest {
	return &ListClientsRequest{
		ClientName: cn,
		Owner:      owner,
		PaginationMeta: PaginationMeta{
			Page: page,
			Size: size,
		},
	}
}

package identities

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/canonical/identity-platform-admin-ui/internal/monitoring"
	kClient "github.com/ory/kratos-client-go"
	"go.opentelemetry.io/otel/trace"
)

type Service struct {
	kratos kClient.IdentityApi

	tracer  trace.Tracer
	monitor monitoring.MonitorInterface
	logger  logging.LoggerInterface
}

type IdentityData struct {
	Identities []kClient.Identity
	Error      *kClient.GenericError
}

// TODO @shipperizer verify during integration test if this is actually the format
type KratosError struct {
	Error *kClient.GenericError `json:"error,omitempty"`
}

func (s *Service) buildListRequest(ctx context.Context, page, size int64, credID string) kClient.IdentityApiListIdentitiesRequest {
	r := s.kratos.ListIdentities(ctx).Page(page).PerPage(size)

	if credID != "" {
		r = r.CredentialsIdentifier(credID)
	}

	return r
}

func (s *Service) parseError(r *http.Response) *kClient.GenericError {
	gerr := KratosError{Error: kClient.NewGenericErrorWithDefaults()}

	defer r.Body.Close()
	body, _ := io.ReadAll(r.Body)

	if err := json.Unmarshal(body, &gerr); err != nil {
		gerr.Error.SetMessage("unable to parse kratos error response")
		gerr.Error.SetCode(http.StatusInternalServerError)
	}

	return gerr.Error
}

// TODO @shipperizer fix pagination
func (s *Service) ListIdentities(ctx context.Context, page, size int64, credID string) (*IdentityData, error) {
	ctx, span := s.tracer.Start(ctx, "kratos.IdentityApi.ListIdentities")
	defer span.End()

	identities, rr, err := s.kratos.ListIdentitiesExecute(
		s.buildListRequest(ctx, page, size, credID),
	)

	data := new(IdentityData)

	if err != nil {
		s.logger.Error(err)
		data.Error = s.parseError(rr)
	}

	data.Identities = identities

	// TODO @shipperizer check if identities is defaulting to empty slice inside kratos-client
	if data.Identities == nil {
		data.Identities = make([]kClient.Identity, 0)
	}

	return data, err
}

func (s *Service) GetIdentity(ctx context.Context, ID string) (*IdentityData, error) {
	ctx, span := s.tracer.Start(ctx, "kratos.IdentityApi.GetIdentity")
	defer span.End()

	identity, rr, err := s.kratos.GetIdentityExecute(
		s.kratos.GetIdentity(ctx, ID),
	)

	data := new(IdentityData)

	if err != nil {
		s.logger.Error(err)
		data.Error = s.parseError(rr)
	}

	if identity != nil {
		data.Identities = []kClient.Identity{*identity}
	} else {
		data.Identities = []kClient.Identity{}
	}

	return data, err
}

func (s *Service) CreateIdentity(ctx context.Context, bodyID *kClient.CreateIdentityBody) (*IdentityData, error) {
	ctx, span := s.tracer.Start(ctx, "kratos.IdentityApi.CreateIdentity")
	defer span.End()

	if bodyID == nil {
		err := fmt.Errorf("no identity data passed")

		data := new(IdentityData)
		data.Identities = []kClient.Identity{}
		data.Error = s.parseError(nil)
		data.Error.SetMessage(err.Error())

		s.logger.Error(err)

		return data, err
	}

	identity, rr, err := s.kratos.CreateIdentityExecute(
		s.kratos.CreateIdentity(ctx).CreateIdentityBody(*bodyID),
	)

	data := new(IdentityData)

	if err != nil {
		s.logger.Error(err)
		data.Error = s.parseError(rr)
	}

	if identity != nil {
		data.Identities = []kClient.Identity{*identity}
	} else {
		data.Identities = []kClient.Identity{}
	}

	return data, err
}

func (s *Service) UpdateIdentity(ctx context.Context, ID string, bodyID *kClient.UpdateIdentityBody) (*IdentityData, error) {
	ctx, span := s.tracer.Start(ctx, "kratos.IdentityApi.UpdateIdentity")
	defer span.End()
	if ID == "" {
		err := fmt.Errorf("no identity ID passed")

		data := new(IdentityData)
		data.Identities = []kClient.Identity{}
		data.Error = s.parseError(nil)
		data.Error.SetMessage(err.Error())

		s.logger.Error(err)

		return data, err
	}

	if bodyID == nil {
		err := fmt.Errorf("no identity body passed")

		data := new(IdentityData)
		data.Identities = []kClient.Identity{}
		data.Error = s.parseError(nil)
		data.Error.SetMessage(err.Error())

		s.logger.Error(err)

		return data, err
	}

	identity, rr, err := s.kratos.UpdateIdentityExecute(
		s.kratos.UpdateIdentity(ctx, ID).UpdateIdentityBody(*bodyID),
	)

	data := new(IdentityData)

	if err != nil {
		s.logger.Error(err)
		data.Error = s.parseError(rr)
	}

	if identity != nil {
		data.Identities = []kClient.Identity{*identity}
	} else {
		data.Identities = []kClient.Identity{}
	}

	return data, err
}

func (s *Service) DeleteIdentity(ctx context.Context, ID string) (*IdentityData, error) {
	ctx, span := s.tracer.Start(ctx, "kratos.IdentityApi.DeleteIdentity")
	defer span.End()

	rr, err := s.kratos.DeleteIdentityExecute(
		s.kratos.DeleteIdentity(ctx, ID),
	)

	data := new(IdentityData)

	if err != nil {
		s.logger.Error(err)
		data.Error = s.parseError(rr)
	}

	data.Identities = []kClient.Identity{}

	return data, err
}

func NewService(kratos kClient.IdentityApi, tracer trace.Tracer, monitor monitoring.MonitorInterface, logger logging.LoggerInterface) *Service {
	s := new(Service)

	s.kratos = kratos

	s.monitor = monitor
	s.tracer = tracer
	s.logger = logger

	return s
}

package clients

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strconv"

	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/canonical/identity-platform-admin-ui/internal/responses"
	"github.com/go-chi/chi/v5"
)

type API struct {
	service ServiceInterface

	logger logging.LoggerInterface
}

type PaginationLinksResponse struct {
	First string `json:"first,omitempty"`
	Last  string `json:"last,omitempty"`
	Prev  string `json:"prev,omitempty"`
	Next  string `json:"next,omitempty"`
}

func (a *API) RegisterEndpoints(mux *chi.Mux) {
	mux.Get("/api/v0/clients", a.ListClients)
	mux.Post("/api/v0/clients", a.CreateClient)
	mux.Get("/api/v0/clients/{id}", a.GetClient)
	mux.Put("/api/v0/clients/{id}", a.UpdateClient)
	mux.Delete("/api/v0/clients/{id}", a.DeleteClient)
}

func (a *API) WriteJSONResponse(w http.ResponseWriter, data interface{}, msg string, status int, links interface{}, meta interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	r := new(responses.Response)
	r.Data = data
	r.Message = msg
	r.Status = status
	r.Links = links
	r.Meta = meta

	err := json.NewEncoder(w).Encode(r)
	if err != nil {
		a.logger.Errorf("Unexpected error: %s", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
}

func (a *API) GetClient(w http.ResponseWriter, r *http.Request) {
	clientId := chi.URLParam(r, "id")

	res, e := a.service.GetClient(r.Context(), clientId)
	if e != nil {
		a.logger.Errorf("Unexpected error: %s", e)
		a.WriteJSONResponse(w, nil, "Unexpected internal error", http.StatusInternalServerError, nil, nil)
		return
	}
	if res.ServiceError != nil {
		a.WriteJSONResponse(w, res.ServiceError, "Failed to get client", res.ServiceError.StatusCode, nil, nil)
		return
	}

	a.WriteJSONResponse(w, res.Resp, "Client info", http.StatusOK, nil, nil)
}

func (a *API) DeleteClient(w http.ResponseWriter, r *http.Request) {
	clientId := chi.URLParam(r, "id")

	res, e := a.service.DeleteClient(r.Context(), clientId)
	if e != nil {
		a.logger.Errorf("Unexpected error: %s", e)
		a.WriteJSONResponse(w, nil, "Unexpected internal error", http.StatusInternalServerError, nil, nil)
		return
	}
	if res.ServiceError != nil {
		a.WriteJSONResponse(w, res.ServiceError, "Failed to delete client", res.ServiceError.StatusCode, nil, nil)
		return
	}

	a.WriteJSONResponse(w, "", "Client deleted", http.StatusOK, nil, nil)
}

func (a *API) CreateClient(w http.ResponseWriter, r *http.Request) {
	// TODO @nsklikas: Limit request params?
	json_data, err := io.ReadAll(r.Body)
	if err != nil {
		a.WriteJSONResponse(w, nil, "Failed to parse request body", http.StatusBadRequest, nil, nil)
		return
	}
	c, err := a.service.UnmarshalClient(json_data)
	if err != nil {
		a.logger.Debugf("Failed to unmarshal JSON: %s", err)
		a.WriteJSONResponse(w, nil, "Failed to parse request body", http.StatusBadRequest, nil, nil)
		return
	}

	res, e := a.service.CreateClient(r.Context(), c)
	if e != nil {
		a.logger.Errorf("Unexpected error: %s", e)
		a.WriteJSONResponse(w, nil, "Unexpected internal error", http.StatusInternalServerError, nil, nil)
		return
	}
	if res.ServiceError != nil {
		a.WriteJSONResponse(w, res.ServiceError, "Failed to create client", res.ServiceError.StatusCode, nil, nil)
		return
	}

	a.WriteJSONResponse(w, res.Resp, "Created client", http.StatusCreated, nil, nil)
}

func (a *API) UpdateClient(w http.ResponseWriter, r *http.Request) {
	clientId := chi.URLParam(r, "id")

	json_data, err := io.ReadAll(r.Body)
	if err != nil {
		a.logger.Debugf("Failed to read response body: %s", err)
		a.WriteJSONResponse(w, nil, "Failed to parse request body", http.StatusBadRequest, nil, nil)
		return
	}
	// TODO @nsklikas: Limit request params?
	c, err := a.service.UnmarshalClient(json_data)
	if err != nil {
		a.logger.Debugf("Failed to unmarshal JSON: %s", err)
		a.WriteJSONResponse(w, nil, "Failed to parse request body", http.StatusBadRequest, nil, nil)
		return
	}
	c.SetClientId(clientId)

	res, e := a.service.UpdateClient(r.Context(), c)
	if e != nil {
		a.logger.Errorf("Unexpected error: %s", e)
		a.WriteJSONResponse(w, nil, "Unexpected internal error", http.StatusInternalServerError, nil, nil)
		return
	}
	if res.ServiceError != nil {
		a.WriteJSONResponse(w, res.ServiceError, "Failed to update client", res.ServiceError.StatusCode, nil, nil)
		return
	}

	a.WriteJSONResponse(w, res.Resp, "Updated client", http.StatusOK, nil, nil)
}

func (a *API) ListClients(w http.ResponseWriter, r *http.Request) {
	req, err := a.parseListClientsRequest(r)
	if err != nil {
		a.WriteJSONResponse(w, nil, "Failed to parse request", http.StatusBadRequest, nil, nil)
		return
	}

	res, e := a.service.ListClients(r.Context(), req)
	if e != nil {
		a.logger.Errorf("Unexpected error: %s", e)
		a.WriteJSONResponse(w, nil, "Unexpected internal error", http.StatusInternalServerError, nil, nil)
		return
	}
	if res.ServiceError != nil {
		a.WriteJSONResponse(w, res.ServiceError, "Failed to fetch clients", res.ServiceError.StatusCode, nil, nil)
		return
	}

	var links PaginationLinksResponse
	if res.Links != nil {
		links = PaginationLinksResponse{
			First: a.convertLinkToUrl(res.Links.First, r.RequestURI),
			Last:  a.convertLinkToUrl(res.Links.Last, r.RequestURI),
			Next:  a.convertLinkToUrl(res.Links.Next, r.RequestURI),
			Prev:  a.convertLinkToUrl(res.Links.Prev, r.RequestURI),
		}
	}

	a.WriteJSONResponse(w, res.Resp, "List of clients", http.StatusOK, links, res.Meta)
}

func (a *API) parseListClientsRequest(r *http.Request) (*ListClientsRequest, error) {
	q := r.URL.Query()

	cn := q.Get("client_name")
	owner := q.Get("owner")
	page := q.Get("page")
	s := q.Get("size")

	var size int = 200
	if s != "" {
		var err error
		size, err = strconv.Atoi(s)
		if err != nil {
			return nil, err
		}
	}
	return NewListClientsRequest(cn, owner, page, size), nil
}

func (a *API) convertLinkToUrl(l PaginationMeta, u string) string {
	if l.Page == "" {
		return ""
	}
	uu, err := url.Parse(u)
	if err != nil {
		a.logger.Fatal("Failed to parse URL: ", u)
	}

	q := uu.Query()
	q.Set("page", l.Page)
	q.Set("size", strconv.Itoa(l.Size))
	uu.RawQuery = q.Encode()
	return uu.String()
}

func NewAPI(service ServiceInterface, logger logging.LoggerInterface) *API {
	a := new(API)

	a.service = service

	a.logger = logger

	return a
}

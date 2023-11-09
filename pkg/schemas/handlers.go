package schemas

import (
	"encoding/json"
	"io"
	"net/http"

	"github.com/canonical/identity-platform-admin-ui/internal/http/types"
	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/go-chi/chi/v5"
	kClient "github.com/ory/kratos-client-go"
)

const okValue = "ok"

type API struct {
	service ServiceInterface

	logger logging.LoggerInterface
}

func (a *API) RegisterEndpoints(mux *chi.Mux) {
	mux.Get("/api/v0/schemas", a.handleList)
	mux.Get("/api/v0/schemas/{id}", a.handleDetail)
	mux.Post("/api/v0/schemas", a.handleCreate)
	mux.Patch("/api/v0/schemas/{id}", a.handlePartialUpdate)
	mux.Delete("/api/v0/schemas/{id}", a.handleRemove)
	mux.Get("/api/v0/schemas/default", a.handleDetailDefault)
	mux.Put("/api/v0/schemas/default", a.handleUpdateDefault)
}

func (a *API) handleList(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	pagination := types.ParsePagination(r.URL.Query())

	schemas, err := a.service.ListSchemas(r.Context(), pagination.Page, pagination.Size)

	if err != nil {
		rr := a.error(schemas.Error)

		w.WriteHeader(rr.Status)
		json.NewEncoder(w).Encode(rr)

		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(
		types.Response{
			Data:    schemas.IdentitySchemas,
			Message: "List of Identity Schemas",
			Status:  http.StatusOK,
			Meta:    pagination,
		},
	)
}

func (a *API) handleDetail(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	ID := chi.URLParam(r, "id")

	schemas, err := a.service.GetSchema(r.Context(), ID)

	if err != nil {
		rr := a.error(schemas.Error)

		w.WriteHeader(rr.Status)
		json.NewEncoder(w).Encode(rr)

		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(
		types.Response{
			Data:    schemas.IdentitySchemas,
			Message: "Detail of Identity Schemas",
			Status:  http.StatusOK,
		},
	)
}

func (a *API) handlePartialUpdate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	ID := chi.URLParam(r, "id")

	defer r.Body.Close()
	body, err := io.ReadAll(r.Body)

	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(
			types.Response{
				Message: "Error parsing request payload",
				Status:  http.StatusBadRequest,
			},
		)

		return
	}

	schema := new(kClient.IdentitySchemaContainer)
	if err := json.Unmarshal(body, schema); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(
			types.Response{
				Message: "Error parsing JSON payload",
				Status:  http.StatusBadRequest,
			},
		)

		return

	}

	schemas, err := a.service.EditSchema(r.Context(), ID, schema)

	if err != nil {

		rr := types.Response{
			Status:  http.StatusInternalServerError,
			Message: err.Error(),
		}

		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(rr)

		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(
		types.Response{
			Data:    schemas.IdentitySchemas,
			Message: "Updated Identity Schemas",
			Status:  http.StatusOK,
		},
	)
}

func (a *API) handleCreate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	defer r.Body.Close()
	body, err := io.ReadAll(r.Body)

	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(
			types.Response{
				Message: "Error parsing request payload",
				Status:  http.StatusBadRequest,
			},
		)

		return
	}

	schema := new(kClient.IdentitySchemaContainer)
	if err := json.Unmarshal(body, schema); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(
			types.Response{
				Message: "Error parsing JSON payload",
				Status:  http.StatusBadRequest,
			},
		)

		return

	}

	schemas, err := a.service.CreateSchema(r.Context(), schema)

	if err != nil {
		status := http.StatusInternalServerError

		if schemas != nil {
			status = http.StatusConflict
		}

		rr := types.Response{
			Status:  status,
			Message: err.Error(),
		}

		w.WriteHeader(status)
		json.NewEncoder(w).Encode(rr)

		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(
		types.Response{
			Data:    schemas.IdentitySchemas,
			Message: "Created Identity Schemas",
			Status:  http.StatusOK,
		},
	)
}

func (a *API) handleRemove(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	id := chi.URLParam(r, "id")

	err := a.service.DeleteSchema(r.Context(), id)

	if err != nil {

		rr := types.Response{
			Status:  http.StatusInternalServerError,
			Message: err.Error(),
		}

		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(rr)

		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(
		types.Response{
			Data:    nil,
			Message: "Identity Schemas deleted",
			Status:  http.StatusOK,
		},
	)
}

func (a *API) handleDetailDefault(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	defaultSchema, err := a.service.GetDefaultSchema(r.Context())

	if err != nil {
		rr := types.Response{
			Status:  http.StatusInternalServerError,
			Message: err.Error(),
		}

		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(rr)

		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(
		types.Response{
			Data:    defaultSchema,
			Message: "Detail of Default Identity Schema",
			Status:  http.StatusOK,
		},
	)
}

func (a *API) handleUpdateDefault(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	defer r.Body.Close()
	body, err := io.ReadAll(r.Body)

	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(
			types.Response{
				Message: "Error parsing request payload",
				Status:  http.StatusBadRequest,
			},
		)

		return
	}

	schema := new(DefaultSchema)
	if err := json.Unmarshal(body, schema); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(
			types.Response{
				Message: "Error parsing JSON payload",
				Status:  http.StatusBadRequest,
			},
		)

		return

	}

	defaultSchema, err := a.service.UpdateDefaultSchema(r.Context(), schema)

	if err != nil {
		rr := types.Response{
			Status:  http.StatusInternalServerError,
			Message: err.Error(),
		}

		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(rr)

		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(
		types.Response{
			Data:    defaultSchema,
			Message: "Default Identity Schema updated",
			Status:  http.StatusOK,
		},
	)
}

// TODO @shipperizer encapsulate kClient.GenericError into a service error to remove library dependency
func (a *API) error(e *kClient.GenericError) types.Response {
	r := types.Response{
		Status: http.StatusInternalServerError,
	}

	if e.Reason != nil {
		r.Message = *e.Reason
	}

	if e.Code != nil {
		r.Status = int(*e.Code)
	}

	return r

}

func NewAPI(service ServiceInterface, logger logging.LoggerInterface) *API {
	a := new(API)

	a.service = service

	a.logger = logger

	return a
}

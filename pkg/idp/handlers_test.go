package idp

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	reflect "reflect"
	"strings"
	"testing"

	"github.com/canonical/identity-platform-admin-ui/internal/http/types"
	"github.com/go-chi/chi/v5"
	gomock "github.com/golang/mock/gomock"
)

//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_interfaces.go -source=./interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_monitor.go -source=../../internal/monitoring/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_tracing.go go.opentelemetry.io/otel/trace Tracer
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_corev1.go k8s.io/client-go/kubernetes/typed/core/v1 CoreV1Interface,ConfigMapInterface

func TestHandleListSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	idps := []*Configuration{
		{
			ID:           "microsoft_af675f353bd7451588e2b8032e315f6f",
			ClientID:     "af675f35-3bd7-4515-88e2-b8032e315f6f",
			Provider:     "microsoft",
			ClientSecret: "secret-1",
			Tenant:       "e1574293-28de-4e94-87d5-b61c76fc14e1",
			Mapper:       "file:///etc/config/kratos/microsoft_schema.jsonnet",
			Scope:        []string{"email"},
		},
		{
			ID:           "google_18fa2999e6c9475aa49515d933d8e8ce",
			ClientID:     "18fa2999-e6c9-475a-a495-15d933d8e8ce",
			Provider:     "google",
			ClientSecret: "secret-2",
			Mapper:       "file:///etc/config/kratos/google_schema.jsonnet",
			Scope:        []string{"email", "profile"},
		},
		{
			ID:           "aws_18fa2999e6c9475aa49589d941d8e1zy",
			ClientID:     "18fa2999-e6c9-475a-a495-89d941d8e1zy",
			Provider:     "aws",
			ClientSecret: "secret-3",
			Mapper:       "file:///etc/config/kratos/google_schema.jsonnet",
			Scope:        []string{"address", "profile"},
		},
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v0/idps", nil)

	mockService.EXPECT().ListResources(gomock.Any()).Return(idps, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	// duplicate types.Response attribute we care and assign the proper type instead of interface{}
	type Response struct {
		Data []*Configuration `json:"data"`
	}

	rr := new(Response)

	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	// cannot use reflect.DeepEqual on the result because Configuration container a json.RawMessage that doesn't play well with it
	if len(idps) != len(rr.Data) {
		t.Fatalf("invalid result, expected %v providers, got: %v", len(idps), len(rr.Data))
	}

	if !reflect.DeepEqual([]string{idps[0].ID, idps[1].ID, idps[2].ID}, []string{rr.Data[0].ID, rr.Data[1].ID, rr.Data[2].ID}) {
		t.Fatalf("invalid result, expected: %v, got: %v", idps, rr.Data)
	}
}

func TestHandleListFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodGet, "/api/v0/idps", nil)

	mockService.EXPECT().ListResources(gomock.Any()).Return(nil, fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected HTTP status code 500 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

}

func TestHandleDetailSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	idps := []*Configuration{
		{
			ID:           "microsoft_af675f353bd7451588e2b8032e315f6f",
			ClientID:     "af675f35-3bd7-4515-88e2-b8032e315f6f",
			Provider:     "microsoft",
			ClientSecret: "secret-1",
			Tenant:       "e1574293-28de-4e94-87d5-b61c76fc14e1",
			Mapper:       "file:///etc/config/kratos/microsoft_schema.jsonnet",
			Scope:        []string{"email"},
		},
		{
			ID:           "google_18fa2999e6c9475aa49515d933d8e8ce",
			ClientID:     "18fa2999-e6c9-475a-a495-15d933d8e8ce",
			Provider:     "google",
			ClientSecret: "secret-2",
			Mapper:       "file:///etc/config/kratos/google_schema.jsonnet",
			Scope:        []string{"email", "profile"},
		},
		{
			ID:           "aws_18fa2999e6c9475aa49589d941d8e1zy",
			ClientID:     "18fa2999-e6c9-475a-a495-89d941d8e1zy",
			Provider:     "aws",
			ClientSecret: "secret-3",
			Mapper:       "file:///etc/config/kratos/google_schema.jsonnet",
			Scope:        []string{"address", "profile"},
		},
	}

	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/idps/%s", idps[0].ID), nil)

	mockService.EXPECT().GetResource(gomock.Any(), idps[0].ID).Return([]*Configuration{idps[0]}, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	// duplicate types.Response attribute we care and assign the proper type instead of interface{}
	type Response struct {
		Data []*Configuration `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 1 {
		t.Fatalf("invalid result, expected only 1 provider, got %v", rr.Data)
	}

	if rr.Data[0].ID != idps[0].ID {
		t.Fatalf("invalid result, expected: %v, got: %v", idps[0], rr.Data[0])
	}
}

func TestHandleDetailEmpty(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/idps/%s", "random"), nil)

	mockService.EXPECT().GetResource(gomock.Any(), "random").Return([]*Configuration{}, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	// duplicate types.Response attribute we care and assign the proper type instead of interface{}
	type Response struct {
		Data []*Configuration `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 0 {
		t.Fatalf("invalid result, expected no providers, got %v", rr.Data)
	}
}

func TestHandleDetailFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	ID := "test-1"
	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/idps/%s", ID), nil)

	mockService.EXPECT().GetResource(gomock.Any(), ID).Return(nil, fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected HTTP status code 418 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}
}

func TestHandleCreateSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "okta_347646e49b484037b83690b020f9f629"
	c.ClientID = "347646e4-9b48-4037-b836-90b020f9f629"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/idps", bytes.NewReader(payload))

	mockService.EXPECT().CreateResource(gomock.Any(), gomock.Any()).DoAndReturn(
		func(ctx context.Context, idp *Configuration) ([]*Configuration, error) {

			if idp.ID != c.ID {
				t.Fatalf("invalid ID, expected %s got %s", c.ID, idp.ID)
			}

			if idp.ClientID != c.ClientID {
				t.Fatalf("invalid ClientID, expected %s got %s", c.ClientID, idp.ClientID)
			}

			if idp.Provider != c.Provider {
				t.Fatalf("invalid provider, expected %s got %s", c.Provider, idp.Provider)
			}

			return []*Configuration{c}, nil
		},
	)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	// duplicate types.Response attribute we care and assign the proper type instead of interface{}
	type Response struct {
		Data []*Configuration `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 1 {
		t.Fatalf("invalid result, expected only 1 provider, got %v", rr.Data)
	}

	if rr.Data[0].ID != c.ID {
		t.Fatalf("invalid result, expected: %v, got: %v", c, rr.Data[0])
	}
}

func TestHandleCreateFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "okta_347646e49b484037b83690b020f9f629"
	c.ClientID = "347646e4-9b48-4037-b836-90b020f9f629"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	payload, err := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/idps", bytes.NewReader(payload))

	mockService.EXPECT().CreateResource(gomock.Any(), gomock.Any()).DoAndReturn(
		func(ctx context.Context, idp *Configuration) ([]*Configuration, error) {

			if idp.ID != c.ID {
				t.Fatalf("invalid ID, expected %s got %s", c.ID, idp.ID)
			}

			if idp.ClientID != c.ClientID {
				t.Fatalf("invalid ClientID, expected %s got %s", c.ClientID, idp.ClientID)
			}

			if idp.Provider != c.Provider {
				t.Fatalf("invalid provider, expected %s got %s", c.Provider, idp.Provider)
			}

			return nil, fmt.Errorf("error")
		},
	)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected HTTP status code 500 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Status != http.StatusInternalServerError {
		t.Errorf("expected code to be %v got %v", http.StatusInternalServerError, rr.Status)
	}
}

func TestHandleCreateFailsConflict(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "okta_347646e49b484037b83690b020f9f629"
	c.ClientID = "347646e4-9b48-4037-b836-90b020f9f629"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	payload, err := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/idps", bytes.NewReader(payload))

	mockService.EXPECT().CreateResource(gomock.Any(), gomock.Any()).DoAndReturn(
		func(ctx context.Context, idp *Configuration) ([]*Configuration, error) {

			if idp.ID != c.ID {
				t.Fatalf("invalid ID, expected %s got %s", c.ID, idp.ID)
			}

			if idp.ClientID != c.ClientID {
				t.Fatalf("invalid ClientID, expected %s got %s", c.ClientID, idp.ClientID)
			}

			if idp.Provider != c.Provider {
				t.Fatalf("invalid provider, expected %s got %s", c.Provider, idp.Provider)
			}

			return []*Configuration{}, fmt.Errorf("error")
		},
	)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusConflict {
		t.Fatalf("expected HTTP status code 409 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Status != http.StatusConflict {
		t.Errorf("expected code to be %v got %v", http.StatusConflict, rr.Status)
	}
}
func TestHandleCreateFailBadRequest(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodPost, "/api/v0/idps", strings.NewReader("test"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected HTTP status code 400 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Status != http.StatusBadRequest {
		t.Errorf("expected code to be %v got %v", http.StatusBadRequest, rr.Status)
	}
}

func TestHandlePartialUpdateSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "okta_347646e49b484037b83690b020f9f629"
	c.ClientID = "347646e4-9b48-4037-b836-90b020f9f629"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPatch, fmt.Sprintf("/api/v0/idps/%s", c.ID), bytes.NewReader(payload))

	mockService.EXPECT().EditResource(gomock.Any(), c.ID, gomock.Any()).DoAndReturn(
		func(ctx context.Context, ID string, idp *Configuration) ([]*Configuration, error) {

			if ID != c.ID {
				t.Fatalf("invalid ID, expected %s got %s", c.ID, ID)
			}

			if idp.ID != c.ID {
				t.Fatalf("invalid ID, expected %s got %s", c.ID, idp.ID)
			}

			if idp.ClientID != c.ClientID {
				t.Fatalf("invalid ClientID, expected %s got %s", c.ClientID, idp.ClientID)
			}

			if idp.Provider != c.Provider {
				t.Fatalf("invalid provider, expected %s got %s", c.Provider, idp.Provider)
			}

			return []*Configuration{c}, nil
		},
	)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	// duplicate types.Response attribute we care and assign the proper type instead of interface{}
	type Response struct {
		Data []*Configuration `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 1 {
		t.Fatalf("invalid result, expected only 1 provider, got %v", rr.Data)
	}

	if rr.Data[0].ID != c.ID {
		t.Fatalf("invalid result, expected: %v, got: %v", c, rr.Data[0])
	}
}

func TestHandlePartialUpdateFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "okta_347646e49b484037b83690b020f9f629"
	c.ClientID = "347646e4-9b48-4037-b836-90b020f9f629"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPatch, fmt.Sprintf("/api/v0/idps/%s", c.ID), bytes.NewReader(payload))

	mockService.EXPECT().EditResource(gomock.Any(), c.ID, gomock.Any()).DoAndReturn(
		func(ctx context.Context, ID string, idp *Configuration) ([]*Configuration, error) {

			if ID != c.ID {
				t.Fatalf("invalid ID, expected %s got %s", c.ID, ID)
			}

			if idp.ID != c.ID {
				t.Fatalf("invalid ID, expected %s got %s", c.ID, idp.ID)
			}

			if idp.ClientID != c.ClientID {
				t.Fatalf("invalid ClientID, expected %s got %s", c.ClientID, idp.ClientID)
			}

			if idp.Provider != c.Provider {
				t.Fatalf("invalid provider, expected %s got %s", c.Provider, idp.Provider)
			}

			return nil, fmt.Errorf("error")
		},
	)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected HTTP status code 500 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Status != http.StatusInternalServerError {
		t.Errorf("expected code to be %v got %v", http.StatusInternalServerError, rr.Status)
	}
}

func TestHandlePartialUpdateFailBadRequest(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodPatch, "/api/v0/idps/fake", strings.NewReader("test"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected HTTP status code 400 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Status != http.StatusBadRequest {
		t.Errorf("expected code to be %v got %v", http.StatusBadRequest, rr.Status)
	}
}

func TestHandleRemoveSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	credID := "test-1"

	req := httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/v0/idps/%s", credID), nil)

	mockService.EXPECT().DeleteResource(gomock.Any(), credID).Return(nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Data != nil {
		t.Fatalf("invalid result, expected no providers, got %v", rr.Data)
	}
	if rr.Status != http.StatusOK {
		t.Errorf("expected code to be %v got %v", http.StatusOK, rr.Status)
	}
}

func TestHandleRemoveFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	credID := "test-1"
	req := httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/v0/idps/%s", credID), nil)

	mockService.EXPECT().DeleteResource(gomock.Any(), credID).Return(fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := io.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected HTTP status code 500 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Status != http.StatusInternalServerError {
		t.Errorf("expected code to be %v got %v", http.StatusInternalServerError, rr.Status)
	}
}

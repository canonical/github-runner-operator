package identities

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"

	"github.com/canonical/identity-platform-admin-ui/internal/http/types"
	"github.com/go-chi/chi/v5"
	gomock "github.com/golang/mock/gomock"

	kClient "github.com/ory/kratos-client-go"
)

//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_interfaces.go -source=./interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_monitor.go -source=../../internal/monitoring/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_tracing.go go.opentelemetry.io/otel/trace Tracer
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_kratos.go github.com/ory/kratos-client-go IdentityApi

func TestHandleListSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	identities := make([]kClient.Identity, 0)

	for i := 0; i < 10; i++ {
		identities = append(identities, *kClient.NewIdentity(fmt.Sprintf("test-%v", i), "test.json", "https://test.com/test.json", map[string]string{"name": "name"}))
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v0/identities", nil)
	values := req.URL.Query()
	values.Add("page", "1")
	values.Add("size", "100")
	req.URL.RawQuery = values.Encode()

	mockService.EXPECT().ListIdentities(gomock.Any(), int64(1), int64(100), "").Return(&IdentityData{Identities: identities}, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

	IDs := make([]kClient.Identity, 0)

	// types.Response.Data is an interface, this means that all needs to be cast step by step
	for _, ii := range rr.Data.([]interface{}) {
		identity := new(kClient.Identity)

		i, ok := ii.(map[string]interface{})

		if !ok {
			t.Errorf("cannot cast to map[string]interface{}")
		}

		identity.Id = i["id"].(string)
		identity.SchemaId = i["schema_id"].(string)
		identity.SchemaUrl = i["schema_url"].(string)

		traits := make(map[string]string, 0)

		for k, v := range i["traits"].(map[string]interface{}) {
			traits[k] = v.(string)
		}

		identity.Traits = traits

		IDs = append(IDs, *identity)
	}

	if !reflect.DeepEqual(IDs, identities) {
		t.Fatalf("invalid result, expected: %v, got: %v", identities, IDs)
	}
}

func TestHandleListFailAndPropagatesKratosError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodGet, "/api/v0/identities", nil)
	values := req.URL.Query()
	values.Add("page", "1")
	values.Add("size", "100")
	req.URL.RawQuery = values.Encode()

	gerr := new(kClient.GenericError)
	gerr.SetCode(http.StatusTeapot)
	gerr.SetMessage("teapot error")
	gerr.SetReason("teapot is broken")

	mockService.EXPECT().ListIdentities(gomock.Any(), int64(1), int64(100), "").Return(&IdentityData{Identities: make([]kClient.Identity, 0), Error: gerr}, fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusTeapot {
		t.Fatalf("expected HTTP status code 418 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Message != *gerr.Reason {
		t.Errorf("expected message to be %s got %s", *gerr.Reason, rr.Message)
	}

	if rr.Status != int(*gerr.Code) {
		t.Errorf("expected code to be %v got %v", *gerr.Code, rr.Status)
	}
}

func TestHandleDetailSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	credID := "test-1"
	identity := kClient.NewIdentity(credID, "test.json", "https://test.com/test.json", map[string]string{"name": "name"})

	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/identities/%s", credID), nil)

	mockService.EXPECT().GetIdentity(gomock.Any(), credID).Return(&IdentityData{Identities: []kClient.Identity{*identity}}, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

	IDs := make([]kClient.Identity, 0)

	// types.Response.Data is an interface, this means that all needs to be cast step by step
	for _, ii := range rr.Data.([]interface{}) {
		identity := new(kClient.Identity)

		i, ok := ii.(map[string]interface{})

		if !ok {
			t.Errorf("cannot cast to map[string]interface{}")
		}

		identity.Id = i["id"].(string)
		identity.SchemaId = i["schema_id"].(string)
		identity.SchemaUrl = i["schema_url"].(string)

		traits := make(map[string]string, 0)

		for k, v := range i["traits"].(map[string]interface{}) {
			traits[k] = v.(string)
		}

		identity.Traits = traits

		IDs = append(IDs, *identity)
	}

	if len(IDs) != 1 {
		t.Fatalf("invalid result, expected only 1 identity, got %v", IDs)
	}

	if !reflect.DeepEqual(IDs[0], *identity) {
		t.Fatalf("invalid result, expected: %v, got: %v", *identity, IDs[0])
	}
}

func TestHandleDetailFailAndPropagatesKratosError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	credID := "test-1"
	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/identities/%s", credID), nil)

	gerr := new(kClient.GenericError)
	gerr.SetCode(http.StatusNotFound)
	gerr.SetMessage("id not found")
	gerr.SetReason("resource missing")

	mockService.EXPECT().GetIdentity(gomock.Any(), credID).Return(&IdentityData{Identities: make([]kClient.Identity, 0), Error: gerr}, fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusNotFound {
		t.Fatalf("expected HTTP status code 418 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Message != *gerr.Reason {
		t.Errorf("expected message to be %s got %s", *gerr.Reason, rr.Message)
	}

	if rr.Status != int(*gerr.Code) {
		t.Errorf("expected code to be %v got %v", *gerr.Code, rr.Status)
	}
}

func TestHandleCreateSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	identity := kClient.NewIdentity("test", "test.json", "https://test.com/test.json", map[string]string{"name": "name"})
	identityBody := kClient.NewCreateIdentityBodyWithDefaults()
	identityBody.SchemaId = identity.SchemaId
	identityBody.Traits = map[string]interface{}{"name": "name"}
	identityBody.AdditionalProperties = map[string]interface{}{"name": "name"}

	payload, _ := json.Marshal(identityBody)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/identities", bytes.NewReader(payload))

	mockService.EXPECT().CreateIdentity(gomock.Any(), identityBody).Return(&IdentityData{Identities: []kClient.Identity{*identity}}, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusCreated {
		t.Fatalf("expected HTTP status code 201 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	IDs := make([]kClient.Identity, 0)

	// types.Response.Data is an interface, this means that all needs to be cast step by step
	for _, ii := range rr.Data.([]interface{}) {
		identity := new(kClient.Identity)

		i, ok := ii.(map[string]interface{})

		if !ok {
			t.Errorf("cannot cast to map[string]interface{}")
		}

		identity.Id = i["id"].(string)
		identity.SchemaId = i["schema_id"].(string)
		identity.SchemaUrl = i["schema_url"].(string)

		traits := make(map[string]string, 0)

		for k, v := range i["traits"].(map[string]interface{}) {
			traits[k] = v.(string)
		}

		identity.Traits = traits

		IDs = append(IDs, *identity)
	}

	if len(IDs) != 1 {
		t.Fatalf("invalid result, expected only 1 identity, got %v", IDs)
	}

	if !reflect.DeepEqual(IDs[0], *identity) {
		t.Fatalf("invalid result, expected: %v, got: %v", *identity, IDs[0])
	}
}

func TestHandleCreateFailAndPropagatesKratosError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	identityBody := kClient.NewCreateIdentityBodyWithDefaults()
	identityBody.SchemaId = "test.json"
	identityBody.Traits = map[string]interface{}{"name": "name"}
	identityBody.AdditionalProperties = map[string]interface{}{"name": "name"}

	payload, err := json.Marshal(identityBody)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/identities", bytes.NewReader(payload))

	gerr := new(kClient.GenericError)
	gerr.SetCode(http.StatusConflict)
	gerr.SetMessage("id already exists")
	gerr.SetReason("conflict")

	mockService.EXPECT().CreateIdentity(gomock.Any(), identityBody).Return(&IdentityData{Identities: make([]kClient.Identity, 0), Error: gerr}, fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

	if rr.Message != *gerr.Reason {
		t.Errorf("expected message to be %s got %s", *gerr.Reason, rr.Message)
	}

	if rr.Status != int(*gerr.Code) {
		t.Errorf("expected code to be %v got %v", *gerr.Code, rr.Status)
	}
}

func TestHandleCreateFailBadRequest(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodPost, "/api/v0/identities", strings.NewReader("test"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

func TestHandleUpdateSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	credID := "test-1"
	identity := kClient.NewIdentity(credID, "test.json", "https://test.com/test.json", map[string]string{"name": "name"})
	identityBody := kClient.NewUpdateIdentityBodyWithDefaults()
	identityBody.SchemaId = identity.SchemaId
	identityBody.SetState(kClient.IDENTITYSTATE_ACTIVE)
	identityBody.Traits = map[string]interface{}{"name": "name"}
	identityBody.AdditionalProperties = map[string]interface{}{"name": "name"}

	payload, _ := json.Marshal(identityBody)

	req := httptest.NewRequest(http.MethodPut, fmt.Sprintf("/api/v0/identities/%s", credID), bytes.NewReader(payload))

	mockService.EXPECT().UpdateIdentity(gomock.Any(), credID, identityBody).Return(&IdentityData{Identities: []kClient.Identity{*identity}}, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

	IDs := make([]kClient.Identity, 0)

	// types.Response.Data is an interface, this means that all needs to be cast step by step
	for _, ii := range rr.Data.([]interface{}) {
		identity := new(kClient.Identity)

		i, ok := ii.(map[string]interface{})

		if !ok {
			t.Errorf("cannot cast to map[string]interface{}")
		}

		identity.Id = i["id"].(string)
		identity.SchemaId = i["schema_id"].(string)
		identity.SchemaUrl = i["schema_url"].(string)

		traits := make(map[string]string, 0)

		for k, v := range i["traits"].(map[string]interface{}) {
			traits[k] = v.(string)
		}

		identity.Traits = traits

		IDs = append(IDs, *identity)
	}

	if len(IDs) != 1 {
		t.Fatalf("invalid result, expected only 1 identity, got %v", IDs)
	}

	if !reflect.DeepEqual(IDs[0], *identity) {
		t.Fatalf("invalid result, expected: %v, got: %v", *identity, IDs[0])
	}
}

func TestHandleUpdateFailAndPropagatesKratosError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	identityBody := kClient.NewUpdateIdentityBodyWithDefaults()
	identityBody.SchemaId = "test.json"
	identityBody.Traits = map[string]interface{}{"name": "name"}
	identityBody.SetState(kClient.IDENTITYSTATE_ACTIVE)
	identityBody.AdditionalProperties = map[string]interface{}{"name": "name"}

	payload, err := json.Marshal(identityBody)
	req := httptest.NewRequest(http.MethodPut, "/api/v0/identities/test", bytes.NewReader(payload))

	gerr := new(kClient.GenericError)
	gerr.SetCode(http.StatusConflict)
	gerr.SetMessage("id already exists")
	gerr.SetReason("conflict")

	mockService.EXPECT().UpdateIdentity(gomock.Any(), "test", identityBody).Return(&IdentityData{Identities: make([]kClient.Identity, 0), Error: gerr}, fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

	if rr.Message != *gerr.Reason {
		t.Errorf("expected message to be %s got %s", *gerr.Reason, rr.Message)
	}

	if rr.Status != int(*gerr.Code) {
		t.Errorf("expected code to be %v got %v", *gerr.Code, rr.Status)
	}
}

func TestHandleUpdateFailBadRequest(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodPut, "/api/v0/identities/test", strings.NewReader("test"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

	req := httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/v0/identities/%s", credID), nil)

	mockService.EXPECT().DeleteIdentity(gomock.Any(), credID).Return(&IdentityData{Identities: make([]kClient.Identity, 0)}, nil)

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

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

	if len(rr.Data.([]interface{})) > 0 {
		t.Fatalf("invalid result, expected no identities, got %v", rr.Data)
	}
	if rr.Status != http.StatusOK {
		t.Errorf("expected code to be %v got %v", http.StatusOK, rr.Status)
	}
}

func TestHandleRemoveFailAndPropagatesKratosError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	credID := "test-1"
	req := httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/v0/identities/%s", credID), nil)

	gerr := new(kClient.GenericError)
	gerr.SetCode(http.StatusNotFound)
	gerr.SetMessage("id not found")
	gerr.SetReason("resource missing")

	mockService.EXPECT().DeleteIdentity(gomock.Any(), credID).Return(&IdentityData{Identities: make([]kClient.Identity, 0), Error: gerr}, fmt.Errorf("error"))

	w := httptest.NewRecorder()
	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	defer res.Body.Close()
	data, err := ioutil.ReadAll(res.Body)

	if err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if res.StatusCode != http.StatusNotFound {
		t.Fatalf("expected HTTP status code 418 got %v", res.StatusCode)
	}

	rr := new(types.Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Message != *gerr.Reason {
		t.Errorf("expected message to be %s got %s", *gerr.Reason, rr.Message)
	}

	if rr.Status != int(*gerr.Code) {
		t.Errorf("expected code to be %v got %v", *gerr.Code, rr.Status)
	}
}

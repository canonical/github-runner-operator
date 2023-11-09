package clients

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	reflect "reflect"
	"testing"

	"github.com/canonical/identity-platform-admin-ui/internal/responses"
	"github.com/go-chi/chi/v5"
	"github.com/golang/mock/gomock"
	hClient "github.com/ory/hydra-client-go/v2"
)

//go:generate mockgen -build_flags=--mod=mod -package clients -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package clients -destination ./mock_clients.go -source=./interfaces.go

func TestHandleGetClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"

	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	resp := NewServiceResponse()
	resp.Resp = c

	req := httptest.NewRequest(http.MethodGet, "/api/v0/clients/"+clientId, nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().GetClient(gomock.Any(), clientId).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	expectedData, _ := c.MarshalJSON()
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	rr, _ := json.Marshal(r.Data)

	if r.Status != http.StatusOK {
		t.Fatal("expected status to be 200, got: ", r.Status)
	}
	if !reflect.DeepEqual(rr, expectedData) {
		t.Fatalf("expected data to be %+v, got: %+v", expectedData, rr)
	}
}

func TestHandleGetClientServiceError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"

	errResp := new(ErrorOAuth2)
	errResp.Error = "Unable to locate the resource"
	resp := NewServiceResponse()
	resp.ServiceError = errResp
	resp.ServiceError.StatusCode = http.StatusNotFound

	req := httptest.NewRequest(http.MethodGet, "/api/v0/clients/"+clientId, nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().GetClient(gomock.Any(), clientId).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusNotFound {
		t.Fatalf("expected HTTP status code 404 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	expectedData, _ := json.Marshal(errResp)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	rr, _ := json.Marshal(r.Data)

	if r.Status != http.StatusNotFound {
		t.Fatal("expected status to be 404, got: ", r.Status)
	}
	if !reflect.DeepEqual(rr, expectedData) {
		t.Fatalf("expected data to be %+v, got: %+v", expectedData, rr)
	}
}

func TestHandleDeleteClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"

	resp := NewServiceResponse()

	req := httptest.NewRequest(http.MethodDelete, "/api/v0/clients/"+clientId, nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().DeleteClient(gomock.Any(), clientId).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	if r.Status != http.StatusOK {
		t.Fatal("expected status to be 200, got: ", r.Status)
	}
}

func TestHandleDeleteClientServiceError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"

	errResp := new(ErrorOAuth2)
	errResp.Error = "Unable to locate the resource"
	resp := NewServiceResponse()
	resp.ServiceError = errResp
	resp.ServiceError.StatusCode = http.StatusNotFound

	req := httptest.NewRequest(http.MethodDelete, "/api/v0/clients/"+clientId, nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().DeleteClient(gomock.Any(), clientId).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusNotFound {
		t.Fatalf("expected HTTP status code 404 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	expectedData, _ := json.Marshal(errResp)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	rr, _ := json.Marshal(r.Data)

	if r.Status != http.StatusNotFound {
		t.Fatal("expected status to be 404, got: ", r.Status)
	}
	if !reflect.DeepEqual(rr, expectedData) {
		t.Fatalf("expected data to be %+v, got: %+v", expectedData, rr)
	}
}

func TestHandleCreateClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	c := hClient.NewOAuth2Client()
	resp := NewServiceResponse()
	resp.Resp = c

	req := httptest.NewRequest(http.MethodPost, "/api/v0/clients", nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().UnmarshalClient(gomock.Any()).Return(c, nil)
	mockService.EXPECT().CreateClient(gomock.Any(), c).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusCreated {
		t.Fatalf("expected HTTP status code 201 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	if r.Status != http.StatusCreated {
		t.Fatal("expected status to be 201, got: ", r.Status)
	}
}

func TestHandleCreateClientServiceError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	c := hClient.NewOAuth2Client()
	errResp := new(ErrorOAuth2)
	errResp.Error = "Some error happened"
	resp := NewServiceResponse()
	resp.ServiceError = errResp
	resp.ServiceError.StatusCode = http.StatusBadRequest

	req := httptest.NewRequest(http.MethodPost, "/api/v0/clients", nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().UnmarshalClient(gomock.Any()).Return(c, nil)
	mockService.EXPECT().CreateClient(gomock.Any(), c).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected HTTP status code 400 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	expectedData, _ := json.Marshal(errResp)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	rr, _ := json.Marshal(r.Data)

	if r.Status != http.StatusBadRequest {
		t.Fatal("expected status to be 400, got: ", r.Status)
	}
	if !reflect.DeepEqual(rr, expectedData) {
		t.Fatalf("expected data to be %+v, got: %+v", expectedData, rr)
	}
}

func TestHandleCreateClientBadRequest(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodPost, "/api/v0/clients", nil)
	w := httptest.NewRecorder()

	mockLogger.EXPECT().Debugf(gomock.Any(), gomock.Any()).Times(1)
	mockService.EXPECT().UnmarshalClient(gomock.Any()).Return(nil, fmt.Errorf("error"))

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected HTTP status code 400 got %v", res.StatusCode)
	}
}

func TestHandleUpdateClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"

	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	resp := NewServiceResponse()
	resp.Resp = c

	req := httptest.NewRequest(http.MethodPut, "/api/v0/clients/"+clientId, nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().UnmarshalClient(gomock.Any()).Return(c, nil)
	mockService.EXPECT().UpdateClient(gomock.Any(), c).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	if r.Status != http.StatusOK {
		t.Fatal("expected status to be 200, got: ", r.Status)
	}
}

func TestHandleUpdateClientServiceError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"

	c := hClient.NewOAuth2Client()
	errResp := new(ErrorOAuth2)
	errResp.Error = "Some error happened"
	resp := NewServiceResponse()
	resp.ServiceError = errResp
	resp.ServiceError.StatusCode = http.StatusBadRequest

	req := httptest.NewRequest(http.MethodPut, "/api/v0/clients/"+clientId, nil)
	w := httptest.NewRecorder()

	mockService.EXPECT().UnmarshalClient(gomock.Any()).Return(c, nil)
	mockService.EXPECT().UpdateClient(gomock.Any(), c).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected HTTP status code 400 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	expectedData, _ := json.Marshal(errResp)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	rr, _ := json.Marshal(r.Data)

	if r.Status != http.StatusBadRequest {
		t.Fatal("expected status to be 404, got: ", r.Status)
	}
	if !reflect.DeepEqual(rr, expectedData) {
		t.Fatalf("expected data to be %+v, got: %+v", expectedData, rr)
	}
}

func TestHandleUpdateClientBadRequest(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"
	req := httptest.NewRequest(http.MethodPut, "/api/v0/clients/"+clientId, nil)
	w := httptest.NewRecorder()

	mockLogger.EXPECT().Debugf(gomock.Any(), gomock.Any()).Times(1)
	mockService.EXPECT().UnmarshalClient(gomock.Any()).Return(nil, fmt.Errorf("error"))

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected HTTP status code 400 got %v", res.StatusCode)
	}
}

func TestHandleListClientsSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	const clientId = "client_id"

	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	resp := NewServiceResponse()
	resp.Resp = []*OAuth2Client{c}

	page := "10"
	size := "10"
	listReq := NewListClientsRequest("", "", page, 10)

	req := httptest.NewRequest(http.MethodGet, "/api/v0/clients", nil)
	q := req.URL.Query()
	q.Set("page", page)
	q.Set("size", size)
	req.URL.RawQuery = q.Encode()
	w := httptest.NewRecorder()

	mockService.EXPECT().ListClients(gomock.Any(), listReq).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusOK {
		t.Fatalf("expected HTTP status code 200 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	if r.Status != http.StatusOK {
		t.Fatal("expected status to be 200, got: ", r.Status)
	}
}

func TestHandleListClientServiceError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	errResp := new(ErrorOAuth2)
	errResp.Error = "Some error happened"
	resp := NewServiceResponse()
	resp.ServiceError = errResp
	resp.ServiceError.StatusCode = http.StatusBadRequest

	page := "10"
	size := "10"
	listReq := NewListClientsRequest("", "", page, 10)

	req := httptest.NewRequest(http.MethodGet, "/api/v0/clients", nil)
	q := req.URL.Query()
	q.Set("page", page)
	q.Set("size", size)
	req.URL.RawQuery = q.Encode()
	w := httptest.NewRecorder()

	mockService.EXPECT().ListClients(gomock.Any(), listReq).Return(resp, nil)

	mux := chi.NewMux()
	NewAPI(mockService, mockLogger).RegisterEndpoints(mux)

	mux.ServeHTTP(w, req)

	res := w.Result()
	if res.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected HTTP status code 400 got %v", res.StatusCode)
	}

	data, err := ioutil.ReadAll(res.Body)
	defer res.Body.Close()

	if err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}

	r := new(responses.Response)
	expectedData, _ := json.Marshal(errResp)
	if err := json.Unmarshal(data, r); err != nil {
		t.Fatalf("expected error to be nil got %v", err)
	}
	rr, _ := json.Marshal(r.Data)

	if r.Status != http.StatusBadRequest {
		t.Fatal("expected status to be 400, got: ", r.Status)
	}
	if !reflect.DeepEqual(rr, expectedData) {
		t.Fatalf("expected data to be %+v, got: %+v", expectedData, rr)
	}
}

package schemas

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
	kClient "github.com/ory/kratos-client-go"
)

//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_interfaces.go -source=./interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_monitor.go -source=../../internal/monitoring/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_tracing.go go.opentelemetry.io/otel/trace Tracer
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_corev1.go k8s.io/client-go/kubernetes/typed/core/v1 CoreV1Interface,ConfigMapInterface
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_kratos.go github.com/ory/kratos-client-go IdentityApi

func TestHandleListSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	v0Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v0.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}
	v1Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v1.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}

	v0ID := "test_v0"
	v1ID := "test_v1"

	schemas := IdentitySchemaData{
		IdentitySchemas: []kClient.IdentitySchemaContainer{
			{
				Id:     &v0ID,
				Schema: v0Schema,
			},
			{
				Id:     &v1ID,
				Schema: v1Schema,
			},
		},
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v0/schemas", nil)

	mockService.EXPECT().ListSchemas(gomock.Any(), int64(1), int64(100)).Return(&schemas, nil)

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
		Data []kClient.IdentitySchemaContainer `json:"data"`
	}

	rr := new(Response)

	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	// cannot use reflect.DeepEqual on the result because Configuration container a json.RawMessage that doesn't play well with it
	if len(schemas.IdentitySchemas) != len(rr.Data) {
		t.Fatalf("invalid result, expected %v schemas, got: %v", len(schemas.IdentitySchemas), len(rr.Data))
	}

	if !reflect.DeepEqual([]string{*schemas.IdentitySchemas[0].Id, *schemas.IdentitySchemas[1].Id}, []string{*rr.Data[0].Id, *rr.Data[1].Id}) {
		t.Fatalf("invalid result, expected: %v, got: %v", schemas.IdentitySchemas, rr.Data)
	}
}

func TestHandleListFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodGet, "/api/v0/schemas", nil)

	gerr := new(kClient.GenericError)
	gerr.SetCode(http.StatusInternalServerError)
	gerr.SetMessage("teapot error")
	gerr.SetReason("teapot is broken")

	mockService.EXPECT().ListSchemas(gomock.Any(), int64(1), int64(100)).Return(&IdentitySchemaData{IdentitySchemas: make([]kClient.IdentitySchemaContainer, 0), Error: gerr}, fmt.Errorf("error"))

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

	v0Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v0.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}

	v0ID := "test_v0"

	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/schemas/%s", v0ID), nil)

	mockService.EXPECT().GetSchema(gomock.Any(), v0ID).Return(
		&IdentitySchemaData{
			IdentitySchemas: []kClient.IdentitySchemaContainer{
				{
					Id:     &v0ID,
					Schema: v0Schema,
				},
			},
		},
		nil,
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
		Data []kClient.IdentitySchemaContainer `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 1 {
		t.Fatalf("invalid result, expected only 1 schema, got %v", rr.Data)
	}

	if *rr.Data[0].Id != v0ID {
		t.Fatalf("invalid result, expected: %v, got: %v", v0ID, rr.Data[0])
	}
}

func TestHandleDetailEmpty(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/schemas/%s", "random"), nil)

	mockService.EXPECT().GetSchema(gomock.Any(), "random").Return(
		&IdentitySchemaData{
			IdentitySchemas: []kClient.IdentitySchemaContainer{},
		},
		nil,
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
		Data []kClient.IdentitySchemaContainer `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 0 {
		t.Fatalf("invalid result, expected no schemas, got %v", rr.Data)
	}
}

func TestHandleDetailFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	ID := "test-1"
	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/v0/schemas/%s", ID), nil)

	gerr := new(kClient.GenericError)
	gerr.SetCode(http.StatusInternalServerError)
	gerr.SetMessage("teapot error")
	gerr.SetReason("teapot is broken")

	mockService.EXPECT().GetSchema(gomock.Any(), ID).Return(&IdentitySchemaData{IdentitySchemas: make([]kClient.IdentitySchemaContainer, 0), Error: gerr}, fmt.Errorf("error"))

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

	v0Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v0.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}

	v0ID := "test_v0"

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/schemas", bytes.NewReader(payload))

	mockService.EXPECT().CreateSchema(gomock.Any(), gomock.Any()).DoAndReturn(
		func(ctx context.Context, schema *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error) {

			if *schema.Id != *c.Id {
				t.Fatalf("invalid ID, expected %s got %s", *c.Id, *schema.Id)
			}

			if !reflect.DeepEqual(schema.Schema, c.Schema) {
				t.Fatalf("invalid schema, expected %s got %s", c.Schema, schema.Schema)
			}

			return &IdentitySchemaData{IdentitySchemas: []kClient.IdentitySchemaContainer{*c}}, nil
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
		Data []kClient.IdentitySchemaContainer `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 1 {
		t.Fatalf("invalid result, expected only 1 schema, got %v", rr.Data)
	}

	if *rr.Data[0].Id != *c.Id {
		t.Fatalf("invalid result, expected: %v, got: %v", c, rr.Data[0])
	}
}

func TestHandleCreateFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	v0Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v0.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}

	v0ID := "test_v0"

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/schemas", bytes.NewReader(payload))

	mockService.EXPECT().CreateSchema(gomock.Any(), gomock.Any()).DoAndReturn(
		func(ctx context.Context, schema *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error) {

			if *schema.Id != *c.Id {
				t.Fatalf("invalid ID, expected %s got %s", *c.Id, *schema.Id)
			}

			if !reflect.DeepEqual(schema.Schema, c.Schema) {
				t.Fatalf("invalid schema, expected %s got %s", c.Schema, schema.Schema)
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

	v0Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v0.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}

	v0ID := "test_v0"

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPost, "/api/v0/schemas", bytes.NewReader(payload))

	mockService.EXPECT().CreateSchema(gomock.Any(), gomock.Any()).DoAndReturn(
		func(ctx context.Context, schema *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error) {

			if *schema.Id != *c.Id {
				t.Fatalf("invalid ID, expected %s got %s", *c.Id, *schema.Id)
			}

			if !reflect.DeepEqual(schema.Schema, c.Schema) {
				t.Fatalf("invalid schema, expected %s got %s", c.Schema, schema.Schema)
			}

			return &IdentitySchemaData{}, fmt.Errorf("error")
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

	req := httptest.NewRequest(http.MethodPost, "/api/v0/schemas", strings.NewReader("test"))

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

	v0Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v0.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}

	v0ID := "test_v0"

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPatch, fmt.Sprintf("/api/v0/schemas/%s", *c.Id), bytes.NewReader(payload))

	mockService.EXPECT().EditSchema(gomock.Any(), *c.Id, gomock.Any()).DoAndReturn(
		func(ctx context.Context, ID string, schema *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error) {
			if ID != *c.Id {
				t.Fatalf("invalid ID, expected %s got %s", *c.Id, ID)
			}

			if *schema.Id != *c.Id {
				t.Fatalf("invalid ID, expected %s got %s", *c.Id, *schema.Id)
			}

			if !reflect.DeepEqual(schema.Schema, c.Schema) {
				t.Fatalf("invalid schema, expected %s got %s", c.Schema, schema.Schema)
			}

			return &IdentitySchemaData{IdentitySchemas: []kClient.IdentitySchemaContainer{*c}}, nil
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
		Data []kClient.IdentitySchemaContainer `json:"data"`
	}

	rr := new(Response)
	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if len(rr.Data) != 1 {
		t.Fatalf("invalid result, expected only 1 schema, got %v", rr.Data)
	}

	if *rr.Data[0].Id != *c.Id {
		t.Fatalf("invalid result, expected: %v, got: %v", c, rr.Data[0])
	}
}

func TestHandlePartialUpdateFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	v0Schema := map[string]interface{}{
		"$id":     "https://schemas.canonical.com/presets/kratos/test_v0.json",
		"$schema": "http://json-schema.org/draft-07/schema#",
		"title":   "Admin Account",
		"type":    "object",
		"properties": map[string]interface{}{
			"traits": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"username": map[string]interface{}{
						"type":  "string",
						"title": "Username",
						"ory.sh/kratos": map[string]interface{}{
							"credentials": map[string]interface{}{
								"password": map[string]interface{}{
									"identifier": true,
								},
							},
						},
					},
				},
			},
		},
		"additionalProperties": true,
	}

	v0ID := "test_v0"

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	payload, _ := json.Marshal(c)
	req := httptest.NewRequest(http.MethodPatch, fmt.Sprintf("/api/v0/schemas/%s", *c.Id), bytes.NewReader(payload))

	mockService.EXPECT().EditSchema(gomock.Any(), *c.Id, gomock.Any()).DoAndReturn(
		func(ctx context.Context, ID string, schema *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error) {
			if ID != *c.Id {
				t.Fatalf("invalid ID, expected %s got %s", *c.Id, ID)
			}

			if *schema.Id != *c.Id {
				t.Fatalf("invalid ID, expected %s got %s", *c.Id, *schema.Id)
			}

			if !reflect.DeepEqual(schema.Schema, c.Schema) {
				t.Fatalf("invalid schema, expected %s got %s", c.Schema, schema.Schema)
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

	req := httptest.NewRequest(http.MethodPatch, "/api/v0/schemas/fake", strings.NewReader("test"))

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

	req := httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/v0/schemas/%s", credID), nil)

	mockService.EXPECT().DeleteSchema(gomock.Any(), credID).Return(nil)

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
		t.Fatalf("invalid result, expected no schemas, got %v", rr.Data)
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
	req := httptest.NewRequest(http.MethodDelete, fmt.Sprintf("/api/v0/schemas/%s", credID), nil)

	mockService.EXPECT().DeleteSchema(gomock.Any(), credID).Return(fmt.Errorf("error"))

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

func TestHandleDetailDefaultSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	defaultSchemaID := "mock_default"
	defaultSchema := new(DefaultSchema)
	defaultSchema.ID = defaultSchemaID

	req := httptest.NewRequest(http.MethodGet, "/api/v0/schemas/default", nil)

	mockService.EXPECT().GetDefaultSchema(gomock.Any()).Return(defaultSchema, nil)

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

	type Response struct {
		Data *DefaultSchema `json:"data"`
	}

	rr := new(Response)

	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Data.ID != defaultSchemaID {
		t.Fatalf("invalid result, expected default id %s, got: %v", defaultSchemaID, rr.Data.ID)
	}
}

func TestHandleDetailDefaultFail(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodGet, "/api/v0/schemas/default", nil)

	mockService.EXPECT().GetDefaultSchema(gomock.Any()).Return(nil, fmt.Errorf("mock_error"))

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
		t.Fatalf("expected HTTP status code %v got %v", http.StatusInternalServerError, res.StatusCode)
	}

	type Response struct {
		Message string `json:"message"`
	}

	rr := new(Response)

	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Message != "mock_error" {
		t.Fatalf("invalid result, expected error message %s, got: %v", "mock_error", rr.Message)
	}
}

func TestHandleUpdateDefaultSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	defaultSchemaID := "mock_default"
	defaultSchema := new(DefaultSchema)
	defaultSchema.ID = defaultSchemaID

	payload, _ := json.Marshal(defaultSchema)

	req := httptest.NewRequest(http.MethodPut, "/api/v0/schemas/default", bytes.NewReader(payload))

	mockService.EXPECT().UpdateDefaultSchema(gomock.Any(), gomock.Any()).Return(defaultSchema, nil)

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

	type Response struct {
		Data *DefaultSchema `json:"data"`
	}

	rr := new(Response)

	if err := json.Unmarshal(data, rr); err != nil {
		t.Errorf("expected error to be nil got %v", err)
	}

	if rr.Data.ID != defaultSchemaID {
		t.Fatalf("invalid result, expected default id %s, got: %v", defaultSchemaID, rr.Data.ID)
	}
}

func TestHandleUpdateDefaultBadRequest(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	req := httptest.NewRequest(http.MethodPut, "/api/v0/schemas/default", strings.NewReader("test"))

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

func TestHandleUpdateDefaultFail(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockService := NewMockServiceInterface(ctrl)

	defaultSchemaID := "mock_default"
	defaultSchema := new(DefaultSchema)
	defaultSchema.ID = defaultSchemaID

	payload, _ := json.Marshal(defaultSchema)

	req := httptest.NewRequest(http.MethodPut, "/api/v0/schemas/default", bytes.NewReader(payload))

	mockService.EXPECT().UpdateDefaultSchema(gomock.Any(), gomock.Any()).DoAndReturn(
		func(ctx context.Context, schema *DefaultSchema) (*DefaultSchema, error) {

			if schema.ID != defaultSchemaID {
				t.Fatalf("invalid ID, expected %s got %s", defaultSchemaID, schema.ID)
			}

			return nil, fmt.Errorf("mock_error")
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

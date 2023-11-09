package schemas

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	reflect "reflect"
	"testing"

	gomock "github.com/golang/mock/gomock"
	kClient "github.com/ory/kratos-client-go"
	"go.opentelemetry.io/otel/trace"
	v1 "k8s.io/api/core/v1"
	metaV1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_interfaces.go -source=./interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_monitor.go -source=../../internal/monitoring/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_tracing.go go.opentelemetry.io/otel/trace Tracer
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_corev1.go k8s.io/client-go/kubernetes/typed/core/v1 CoreV1Interface,ConfigMapInterface
//go:generate mockgen -build_flags=--mod=mod -package schemas -destination ./mock_kratos.go github.com/ory/kratos-client-go IdentityApi

func TestListSchemasSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &v0ID,
			Schema: v0Schema,
		},
		{
			Id:     &v1ID,
			Schema: v1Schema,
		},
	}

	identitySchemaRequest := kClient.IdentityApiListIdentitySchemasRequest{
		ApiService: mockKratosIdentityApi,
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.ListSchemas").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().ListIdentitySchemas(ctx).Times(1).Return(identitySchemaRequest)
	mockKratosIdentityApi.EXPECT().ListIdentitySchemasExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiListIdentitySchemasRequest) ([]kClient.IdentitySchemaContainer, *http.Response, error) {

			// use reflect as attributes are private, also are pointers so need to cast it multiple times
			if page := (*int64)(reflect.ValueOf(r).FieldByName("page").UnsafePointer()); *page != 1 {
				t.Fatalf("expected page as 1, got %v", *page)
			}

			if pageSize := (*int64)(reflect.ValueOf(r).FieldByName("perPage").UnsafePointer()); *pageSize != 10 {
				t.Fatalf("expected page size as 10, got %v", *pageSize)
			}

			return schemas, new(http.Response), nil
		},
	)
	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).ListSchemas(ctx, 1, 10)

	if !reflect.DeepEqual(is.IdentitySchemas, schemas) {
		t.Fatalf("expected schemas to be %v not  %v", schemas, is.IdentitySchemas)

	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestListSchemasFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	identitySchemaRequest := kClient.IdentityApiListIdentitySchemasRequest{
		ApiService: mockKratosIdentityApi,
	}

	schemas := make([]kClient.IdentitySchemaContainer, 0)

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "schemas.Service.ListSchemas").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockTracer.EXPECT().Start(ctx, "schemas.Service.parseError").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().ListIdentitySchemas(ctx).Times(1).Return(identitySchemaRequest)
	mockKratosIdentityApi.EXPECT().ListIdentitySchemasExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiListIdentitySchemasRequest) ([]kClient.IdentitySchemaContainer, *http.Response, error) {

			// use reflect as attributes are private, also are pointers so need to cast it multiple times
			if page := (*int64)(reflect.ValueOf(r).FieldByName("page").UnsafePointer()); *page != 1 {
				t.Fatalf("expected page as 1, got %v", *page)
			}

			if pageSize := (*int64)(reflect.ValueOf(r).FieldByName("perPage").UnsafePointer()); *pageSize != 10 {
				t.Fatalf("expected page size as 10, got %v", *pageSize)
			}

			rr := httptest.NewRecorder()
			rr.Header().Set("Content-Type", "application/json")
			rr.WriteHeader(http.StatusInternalServerError)

			json.NewEncoder(rr).Encode(
				map[string]interface{}{
					"error": map[string]interface{}{
						"code":    http.StatusInternalServerError,
						"debug":   "--------",
						"details": map[string]interface{}{},
						"id":      "string",
						"message": "error",
						"reason":  "error",
						"request": "d7ef54b1-ec15-46e6-bccb-524b82c035e6",
						"status":  "Not Found",
					},
				},
			)

			return schemas, rr.Result(), fmt.Errorf("error")
		},
	)
	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).ListSchemas(ctx, 1, 10)

	if is.Error == nil {
		t.Fatal("expected ids.Error to be not nil")
	}

	if *is.Error.Code != http.StatusInternalServerError {
		t.Fatalf("expected code to be %v not  %v", http.StatusInternalServerError, *is.Error.Code)
	}

	if err == nil {
		t.Fatal("expected error to be not nil")
	}
}

func TestListSchemasSuccessButEmpty(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	schemas := []kClient.IdentitySchemaContainer{}

	identitySchemaRequest := kClient.IdentityApiListIdentitySchemasRequest{
		ApiService: mockKratosIdentityApi,
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.ListSchemas").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().ListIdentitySchemas(ctx).Times(1).Return(identitySchemaRequest)
	mockKratosIdentityApi.EXPECT().ListIdentitySchemasExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiListIdentitySchemasRequest) ([]kClient.IdentitySchemaContainer, *http.Response, error) {

			// use reflect as attributes are private, also are pointers so need to cast it multiple times
			if page := (*int64)(reflect.ValueOf(r).FieldByName("page").UnsafePointer()); *page != 1 {
				t.Fatalf("expected page as 1, got %v", *page)
			}

			if pageSize := (*int64)(reflect.ValueOf(r).FieldByName("perPage").UnsafePointer()); *pageSize != 10 {
				t.Fatalf("expected page size as 10, got %v", *pageSize)
			}

			return schemas, new(http.Response), nil
		},
	)
	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).ListSchemas(ctx, 1, 10)

	if !reflect.DeepEqual(is.IdentitySchemas, schemas) {
		t.Fatalf("expected schemas to be %v not  %v", schemas, is.IdentitySchemas)

	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetSchemaSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	identitySchemaRequest := kClient.IdentityApiGetIdentitySchemaRequest{
		ApiService: mockKratosIdentityApi,
	}

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

	schema := kClient.IdentitySchemaContainer{
		Id:     &v0ID,
		Schema: v0Schema,
	}
	mockTracer.EXPECT().Start(ctx, "schemas.Service.GetSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().GetIdentitySchema(ctx, v0ID).Times(1).Return(identitySchemaRequest)
	mockKratosIdentityApi.EXPECT().GetIdentitySchemaExecute(gomock.Any()).Times(1).Return(schema.Schema, new(http.Response), nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetSchema(ctx, v0ID)

	if !reflect.DeepEqual(is.IdentitySchemas, []kClient.IdentitySchemaContainer{schema}) {
		t.Fatalf("expected schemas to be %v not  %v", schema, is.IdentitySchemas)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetSchemaSuccessButEmpty(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	identitySchemaRequest := kClient.IdentityApiGetIdentitySchemaRequest{
		ApiService: mockKratosIdentityApi,
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.GetSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().GetIdentitySchema(ctx, "test").Times(1).Return(identitySchemaRequest)
	mockKratosIdentityApi.EXPECT().GetIdentitySchemaExecute(gomock.Any()).Times(1).Return(nil, new(http.Response), nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetSchema(ctx, "test")

	if !reflect.DeepEqual(is.IdentitySchemas, []kClient.IdentitySchemaContainer{}) {
		t.Fatalf("expected schemas to be empty not  %v", is.IdentitySchemas)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetSchemaFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	identitySchemaRequest := kClient.IdentityApiGetIdentitySchemaRequest{
		ApiService: mockKratosIdentityApi,
	}

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "schemas.Service.GetSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockTracer.EXPECT().Start(ctx, "schemas.Service.parseError").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().GetIdentitySchema(ctx, "fake").Times(1).Return(identitySchemaRequest)
	mockKratosIdentityApi.EXPECT().GetIdentitySchemaExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiGetIdentitySchemaRequest) (map[string]interface{}, *http.Response, error) {
			rr := httptest.NewRecorder()
			rr.Header().Set("Content-Type", "application/json")
			rr.WriteHeader(http.StatusNotFound)

			json.NewEncoder(rr).Encode(
				map[string]interface{}{
					"error": map[string]interface{}{
						"code":    http.StatusNotFound,
						"debug":   "--------",
						"details": map[string]interface{}{},
						"id":      "string",
						"message": "error",
						"reason":  "error",
						"request": "d7ef54b1-ec15-46e6-bccb-524b82c035e6",
						"status":  "Not Found",
					},
				},
			)

			return nil, rr.Result(), fmt.Errorf("error")
		},
	)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetSchema(ctx, "fake")

	if !reflect.DeepEqual(is.IdentitySchemas, make([]kClient.IdentitySchemaContainer, 0)) {
		t.Fatalf("expected schemas to be empty not  %v", is.IdentitySchemas)
	}

	if is.Error == nil {
		t.Fatal("expected is.Error to be not nil")
	}

	if *is.Error.Code != int64(http.StatusNotFound) {
		t.Fatalf("expected code to be %v not  %v", http.StatusNotFound, *is.Error.Code)
	}

	if err == nil {
		t.Fatal("expected error to be not nil")
	}
}

func TestEdiSchemaSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &v0ID,
			Schema: v0Schema,
		},
		{
			Id:     &v1ID,
			Schema: v1Schema,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = map[string]interface{}{
		"test": "test",
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.EditSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).EditSchema(ctx, v0ID, c)

	if !reflect.DeepEqual(is.IdentitySchemas[0].Schema, c.Schema) {
		t.Fatalf("expected schema secret to be %v not  %v", c.Schema, is.IdentitySchemas[0].Schema)

	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestEditSchemaNotfound(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &v0ID,
			Schema: v0Schema,
		},
		{
			Id:     &v1ID,
			Schema: v1Schema,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}

	ID := "fake"

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &ID
	c.Schema = map[string]interface{}{
		"test": "test",
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.EditSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).EditSchema(ctx, "fake", c)

	if len(is.IdentitySchemas) != 0 {
		t.Fatalf("expected schemas to be empty not  %v", is.IdentitySchemas)
	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestEditSchemaFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	rawSchema, _ := json.Marshal(v0Schema)
	cm.Data[v0ID] = string(rawSchema)

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = map[string]interface{}{
		"test": "test",
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.EditSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).Return(cm, fmt.Errorf("error"))

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).EditSchema(ctx, v0ID, c)

	if is != nil {
		t.Fatalf("expected schemas to be nil, not %v", is)
	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestCreateSchemaSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	mockTracer.EXPECT().Start(ctx, "schemas.Service.CreateSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			i := new(kClient.IdentitySchemaContainer)

			rawSchema, _ := configMap.Data[*c.Id]

			_ = json.Unmarshal([]byte(rawSchema), &i.Schema)

			if !reflect.DeepEqual(i.Schema, v0Schema) {
				t.Fatalf("expected schema to be %v not %v", v0Schema, i.Schema)
			}

			if *c.Id != v0ID {
				t.Fatalf("expected schema ID to be %v not %v", v0ID, i.Id)
			}

			return cm, nil
		},
	)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).CreateSchema(ctx, c)

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}

	if !reflect.DeepEqual(is.IdentitySchemas[0].Schema, v0Schema) {
		t.Fatalf("expected schema to be %v not %v", v0Schema, is.IdentitySchemas[0].Schema)
	}

	if *is.IdentitySchemas[0].Id != v0ID {
		t.Fatalf("expected schema ID to be %v not %v", v0ID, is.IdentitySchemas[0].Id)
	}

}

func TestCreateSchemaFailsConflict(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	rawSchema, _ := json.Marshal(v0Schema)
	cm.Data[v0ID] = string(rawSchema)

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	mockTracer.EXPECT().Start(ctx, "schemas.Service.CreateSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).CreateSchema(ctx, c)

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}

	if len(is.IdentitySchemas) != 0 {
		t.Fatalf("expected schemas to be empty not %v", is.IdentitySchemas[0].Schema)
	}

}

func TestCreateSchemaFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)

	c := new(kClient.IdentitySchemaContainer)
	c.Id = &v0ID
	c.Schema = v0Schema

	mockTracer.EXPECT().Start(ctx, "schemas.Service.CreateSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			i := new(kClient.IdentitySchemaContainer)

			rawSchema, _ := configMap.Data[*c.Id]

			_ = json.Unmarshal([]byte(rawSchema), &i.Schema)

			if !reflect.DeepEqual(i.Schema, v0Schema) {
				t.Fatalf("expected schema to be %v not %v", v0Schema, i.Schema)
			}

			if *c.Id != v0ID {
				t.Fatalf("expected schema ID to be %v not %v", v0ID, i.Id)
			}

			return nil, fmt.Errorf("error")
		},
	)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).CreateSchema(ctx, c)

	if is != nil {
		t.Fatalf("expected schema to be empty not %v", is.IdentitySchemas)
	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestDeleteSchemaSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &v0ID,
			Schema: v0Schema,
		},
		{
			Id:     &v1ID,
			Schema: v1Schema,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.DeleteSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			if _, ok := cm.Data[v0ID]; ok {
				t.Fatalf("expected key %s to be deleted", v0ID)
			}

			return cm, nil
		},
	)

	err := NewService(cfg, mockTracer, mockMonitor, mockLogger).DeleteSchema(ctx, v0ID)

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestDeleteSchemaNotFound(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &v0ID,
			Schema: v0Schema,
		},
		{
			Id:     &v1ID,
			Schema: v1Schema,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.DeleteSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	err := NewService(cfg, mockTracer, mockMonitor, mockLogger).DeleteSchema(ctx, "fake")

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestDeleteSchemaFailsIfDefault(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &v0ID,
			Schema: v0Schema,
		},
		{
			Id:     &v1ID,
			Schema: v1Schema,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}
	cm.Data[DEFAULT_SCHEMA] = v0ID

	mockTracer.EXPECT().Start(ctx, "schemas.Service.DeleteSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	err := NewService(cfg, mockTracer, mockMonitor, mockLogger).DeleteSchema(ctx, DEFAULT_SCHEMA)

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestDeleteSchemaFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

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

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &v0ID,
			Schema: v0Schema,
		},
		{
			Id:     &v1ID,
			Schema: v1Schema,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.DeleteSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			return nil, fmt.Errorf("error")
		},
	)
	err := NewService(cfg, mockTracer, mockMonitor, mockLogger).DeleteSchema(ctx, v0ID)

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestGetDefaultSchemaSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	defaultSchemaID := "mock_default"
	defaultSchema := new(DefaultSchema)
	defaultSchema.ID = defaultSchemaID

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[DEFAULT_SCHEMA] = defaultSchemaID

	mockTracer.EXPECT().Start(ctx, "schemas.Service.GetDefaultSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	ds, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetDefaultSchema(ctx)

	if ds.ID != defaultSchemaID {
		t.Fatalf("expected default schema id to be %s not %s", defaultSchemaID, ds.ID)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetDefaultSchemaNoDefaultSchema(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	defaultSchemaID := "mock_default"
	defaultSchema := new(DefaultSchema)
	defaultSchema.ID = defaultSchemaID

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data["wrong_key"] = defaultSchemaID

	error_msg := fmt.Sprintf("default schema %s missing", DEFAULT_SCHEMA)

	mockTracer.EXPECT().Start(ctx, "schemas.Service.GetDefaultSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	ds, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetDefaultSchema(ctx)

	if ds != nil {
		t.Fatalf("expected returned value to be nil not %s", ds)
	}

	if err.Error() != error_msg {
		t.Fatalf("expected error to be %s not  %s", error_msg, err.Error())
	}
}

func TestGetDefaultSchemaFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "schemas.Service.GetDefaultSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(nil, fmt.Errorf("mock_error"))

	ds, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetDefaultSchema(ctx)

	if ds != nil {
		t.Fatalf("expected returned value to be nil not %s", ds)
	}

	if err.Error() != "mock_error" {
		t.Fatalf("expected error to be mock_error not %s", err.Error())
	}
}

func TestUpdateDefaultSchemaSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	defaultSchemaID := "mock_default"
	defaultSchemaUpdateID := "mock_update"
	defaultSchemaUpdate := new(DefaultSchema)
	defaultSchemaUpdate.ID = defaultSchemaUpdateID

	schema1 := map[string]interface{}{
		"$id": "mock_default",
	}
	schemaId1 := "mock_default"
	schema2 := map[string]interface{}{
		"$id": "mock_update",
	}
	schemaId2 := "mock_update"

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &schemaId1,
			Schema: schema1,
		},
		{
			Id:     &schemaId2,
			Schema: schema2,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[DEFAULT_SCHEMA] = defaultSchemaID
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.UpdateDefaultSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			if configMap.Data[DEFAULT_SCHEMA] != defaultSchemaUpdateID {
				t.Fatalf("expected default schema id to be %s not %s", defaultSchemaUpdateID, configMap.Data[DEFAULT_SCHEMA])
			}

			return cm, nil
		},
	)

	ds, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).UpdateDefaultSchema(ctx, defaultSchemaUpdate)

	if ds.ID != defaultSchemaUpdateID {
		t.Fatalf("expected default schema id to be %s not %s", defaultSchemaID, ds.ID)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestUpdateDefaultSchemaIdNotFound(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	defaultSchemaID := "mock_default"
	defaultSchemaUpdateID := "mock_update"
	defaultSchemaUpdate := new(DefaultSchema)
	defaultSchemaUpdate.ID = defaultSchemaUpdateID

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[DEFAULT_SCHEMA] = defaultSchemaID

	mockTracer.EXPECT().Start(ctx, "schemas.Service.UpdateDefaultSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	ds, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).UpdateDefaultSchema(ctx, defaultSchemaUpdate)

	if ds != nil {
		t.Fatalf("expected default schema id to be nil not %s", ds.ID)
	}

	error_msg := fmt.Sprintf("schema with ID %s not available", defaultSchemaUpdateID)
	if err.Error() != error_msg {
		t.Fatalf("expected error to be %s not  %s", error_msg, err.Error())
	}
}

func TestUpdateDefaultSchemaIdIsDefaultKey(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	defaultSchemaID := "mock_default"
	defaultSchemaUpdateID := DEFAULT_SCHEMA
	defaultSchemaUpdate := new(DefaultSchema)
	defaultSchemaUpdate.ID = defaultSchemaUpdateID

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[DEFAULT_SCHEMA] = defaultSchemaID

	mockTracer.EXPECT().Start(ctx, "schemas.Service.UpdateDefaultSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	ds, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).UpdateDefaultSchema(ctx, defaultSchemaUpdate)

	if ds != nil {
		t.Fatalf("expected default schema id to be nil not %s", ds.ID)
	}

	error_msg := fmt.Sprintf("schema with ID %s not available", defaultSchemaUpdateID)
	if err.Error() != error_msg {
		t.Fatalf("expected error to be %s not  %s", error_msg, err.Error())
	}
}

func TestUpdateDefaultSchemaFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.Kratos = mockKratosIdentityApi
	cfg.Name = "schemas"
	cfg.Namespace = "default"

	defaultSchemaID := "mock_default"
	defaultSchemaUpdateID := "mock_update"
	defaultSchemaUpdate := new(DefaultSchema)
	defaultSchemaUpdate.ID = defaultSchemaUpdateID

	schema1 := map[string]interface{}{
		"$id": "mock_default",
	}
	schemaId1 := "mock_default"
	schema2 := map[string]interface{}{
		"$id": "mock_update",
	}
	schemaId2 := "mock_update"

	schemas := []kClient.IdentitySchemaContainer{
		{
			Id:     &schemaId1,
			Schema: schema1,
		},
		{
			Id:     &schemaId2,
			Schema: schema2,
		},
	}

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[DEFAULT_SCHEMA] = defaultSchemaID
	for _, sc := range schemas {
		rawSchema, _ := json.Marshal(sc.Schema)

		cm.Data[*sc.Id] = string(rawSchema)
	}

	mockTracer.EXPECT().Start(ctx, "schemas.Service.UpdateDefaultSchema").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			if configMap.Data[DEFAULT_SCHEMA] != defaultSchemaUpdateID {
				t.Fatalf("expected default schema id to be %s not %s", defaultSchemaUpdateID, configMap.Data[DEFAULT_SCHEMA])
			}

			return nil, fmt.Errorf("mock_error")
		},
	)

	_, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).UpdateDefaultSchema(ctx, defaultSchemaUpdate)

	if err.Error() != "mock_error" {
		t.Fatalf("expected error message to be mock_error not  %s", err.Error())
	}
}

package identities

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
)

//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_interfaces.go -source=./interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_monitor.go -source=../../internal/monitoring/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_tracing.go go.opentelemetry.io/otel/trace Tracer
//go:generate mockgen -build_flags=--mod=mod -package identities -destination ./mock_kratos.go github.com/ory/kratos-client-go IdentityApi

func TestListIdentitiesSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()

	identityRequest := kClient.IdentityApiListIdentitiesRequest{
		ApiService: mockKratosIdentityApi,
	}

	identities := make([]kClient.Identity, 0)

	for i := 0; i < 10; i++ {
		identities = append(identities, *kClient.NewIdentity(fmt.Sprintf("test-%v", i), "test.json", "https://test.com/test.json", map[string]string{"name": "name"}))
	}

	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.ListIdentities").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().ListIdentities(ctx).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().ListIdentitiesExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiListIdentitiesRequest) ([]kClient.Identity, *http.Response, error) {

			// use reflect as attributes are private, also are pointers so need to cast it multiple times
			if page := (*int64)(reflect.ValueOf(r).FieldByName("page").UnsafePointer()); *page != 2 {
				t.Fatalf("expected page as 2, got %v", *page)
			}

			if pageSize := (*int64)(reflect.ValueOf(r).FieldByName("perPage").UnsafePointer()); *pageSize != 10 {
				t.Fatalf("expected page size as 10, got %v", *pageSize)
			}

			if credID := (*string)(reflect.ValueOf(r).FieldByName("credentialsIdentifier").UnsafePointer()); credID != nil {
				t.Fatalf("expected credential id to be empty, got %v", *credID)
			}

			return identities, new(http.Response), nil
		},
	)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).ListIdentities(ctx, 2, 10, "")

	if !reflect.DeepEqual(ids.Identities, identities) {
		t.Fatalf("expected identities to be %v not  %v", identities, ids.Identities)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestListIdentitiesFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()

	identityRequest := kClient.IdentityApiListIdentitiesRequest{
		ApiService: mockKratosIdentityApi,
	}

	identities := make([]kClient.Identity, 0)

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.ListIdentities").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().ListIdentities(ctx).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().ListIdentitiesExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiListIdentitiesRequest) ([]kClient.Identity, *http.Response, error) {

			// use reflect as attributes are private, also are pointers so need to cast it multiple times
			if page := (*int64)(reflect.ValueOf(r).FieldByName("page").UnsafePointer()); *page != 2 {
				t.Fatalf("expected page as 2, got %v", *page)
			}

			if pageSize := (*int64)(reflect.ValueOf(r).FieldByName("perPage").UnsafePointer()); *pageSize != 10 {
				t.Fatalf("expected page size as 10, got %v", *pageSize)
			}

			if credID := (*string)(reflect.ValueOf(r).FieldByName("credentialsIdentifier").UnsafePointer()); *credID != "test" {
				t.Fatalf("expected credential id to be test, got %v", *credID)
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

			return identities, rr.Result(), fmt.Errorf("error")
		},
	)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).ListIdentities(ctx, 2, 10, "test")

	if !reflect.DeepEqual(ids.Identities, identities) {
		t.Fatalf("expected identities to be empty not  %v", ids.Identities)
	}

	if ids.Error == nil {
		t.Fatal("expected ids.Error to be not nil")
	}

	if *ids.Error.Code != http.StatusInternalServerError {
		t.Fatalf("expected code to be %v not  %v", http.StatusInternalServerError, *ids.Error.Code)
	}

	if err == nil {
		t.Fatal("expected error to be not nil")
	}
}

func TestGetIdentitySuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()
	credID := "test-1"

	identityRequest := kClient.IdentityApiGetIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	identity := kClient.NewIdentity(credID, "test.json", "https://test.com/test.json", map[string]string{"name": "name"})

	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.GetIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().GetIdentity(ctx, credID).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().GetIdentityExecute(gomock.Any()).Times(1).Return(identity, new(http.Response), nil)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).GetIdentity(ctx, credID)

	if !reflect.DeepEqual(ids.Identities, []kClient.Identity{*identity}) {
		t.Fatalf("expected identities to be %v not  %v", *identity, ids.Identities)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetIdentityFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()
	credID := "test"

	identityRequest := kClient.IdentityApiGetIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.GetIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().GetIdentity(ctx, credID).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().GetIdentityExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiGetIdentityRequest) (*kClient.Identity, *http.Response, error) {
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

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).GetIdentity(ctx, credID)

	if !reflect.DeepEqual(ids.Identities, make([]kClient.Identity, 0)) {
		t.Fatalf("expected identities to be empty not  %v", ids.Identities)
	}

	if ids.Error == nil {
		t.Fatal("expected ids.Error to be not nil")
	}

	if *ids.Error.Code != int64(http.StatusNotFound) {
		t.Fatalf("expected code to be %v not  %v", http.StatusNotFound, *ids.Error.Code)
	}

	if err == nil {
		t.Fatal("expected error to be not nil")
	}
}

func TestCreateIdentitySuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()

	identityRequest := kClient.IdentityApiCreateIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	identity := kClient.NewIdentity("test", "test.json", "https://test.com/test.json", map[string]string{"name": "name"})
	credentials := kClient.NewIdentityWithCredentialsWithDefaults()
	identityBody := kClient.NewCreateIdentityBody("test.json", map[string]interface{}{"name": "name"})
	identityBody.SetCredentials(*credentials)

	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.CreateIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().CreateIdentity(ctx).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().CreateIdentityExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiCreateIdentityRequest) (*kClient.Identity, *http.Response, error) {

			// use reflect as attributes are private, also are pointers so need to cast it multiple times
			if IDBody := (*kClient.CreateIdentityBody)(reflect.ValueOf(r).FieldByName("createIdentityBody").UnsafePointer()); !reflect.DeepEqual(*IDBody, *identityBody) {
				t.Fatalf("expected body to be %v, got %v", identityBody, IDBody)
			}

			return identity, new(http.Response), nil
		},
	)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).CreateIdentity(ctx, identityBody)

	if !reflect.DeepEqual(ids.Identities, []kClient.Identity{*identity}) {
		t.Fatalf("expected identities to be %v not  %v", *identity, ids.Identities)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestCreateIdentityFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()

	identityRequest := kClient.IdentityApiCreateIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	credentials := kClient.NewIdentityWithCredentialsWithDefaults()
	identityBody := kClient.NewCreateIdentityBody("test.json", map[string]interface{}{"name": "name"})
	identityBody.SetCredentials(*credentials)

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.CreateIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().CreateIdentity(ctx).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().CreateIdentityExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiCreateIdentityRequest) (*kClient.Identity, *http.Response, error) {
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
						"status":  "Internal Server Error",
					},
				},
			)

			return nil, rr.Result(), fmt.Errorf("error")
		},
	)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).CreateIdentity(ctx, identityBody)

	if !reflect.DeepEqual(ids.Identities, make([]kClient.Identity, 0)) {
		t.Fatalf("expected identities to be empty not  %v", ids.Identities)
	}

	if ids.Error == nil {
		t.Fatal("expected ids.Error to be not nil")
	}

	if *ids.Error.Code != int64(http.StatusInternalServerError) {
		t.Fatalf("expected code to be %v not  %v", http.StatusInternalServerError, *ids.Error.Code)
	}

	if err == nil {
		t.Fatal("expected error to be not nil")
	}
}

func TestUpdateIdentitySuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()

	identityRequest := kClient.IdentityApiUpdateIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	identity := kClient.NewIdentity("test", "test.json", "https://test.com/test.json", map[string]string{"name": "name"})
	credentials := kClient.NewIdentityWithCredentialsWithDefaults()
	identityBody := kClient.NewUpdateIdentityBodyWithDefaults()
	identityBody.SetTraits(map[string]interface{}{"name": "name"})
	identityBody.SetCredentials(*credentials)

	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.UpdateIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().UpdateIdentity(ctx, identity.Id).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().UpdateIdentityExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiUpdateIdentityRequest) (*kClient.Identity, *http.Response, error) {

			// use reflect as attributes are private, also are pointers so need to cast it multiple times
			if IDBody := (*kClient.UpdateIdentityBody)(reflect.ValueOf(r).FieldByName("updateIdentityBody").UnsafePointer()); !reflect.DeepEqual(*IDBody, *identityBody) {
				t.Fatalf("expected body to be %v, got %v", identityBody, IDBody)
			}

			return identity, new(http.Response), nil
		},
	)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).UpdateIdentity(ctx, identity.Id, identityBody)

	if !reflect.DeepEqual(ids.Identities, []kClient.Identity{*identity}) {
		t.Fatalf("expected identities to be %v not  %v", *identity, ids.Identities)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestUpdateIdentityFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()

	credID := "test"

	identityRequest := kClient.IdentityApiUpdateIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	credentials := kClient.NewIdentityWithCredentialsWithDefaults()
	identityBody := kClient.NewUpdateIdentityBodyWithDefaults()
	identityBody.SetTraits(map[string]interface{}{"name": "name"})
	identityBody.SetCredentials(*credentials)

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.UpdateIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().UpdateIdentity(ctx, credID).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().UpdateIdentityExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiUpdateIdentityRequest) (*kClient.Identity, *http.Response, error) {
			rr := httptest.NewRecorder()
			rr.Header().Set("Content-Type", "application/json")
			rr.WriteHeader(http.StatusConflict)

			json.NewEncoder(rr).Encode(
				map[string]interface{}{
					"error": map[string]interface{}{
						"code":    http.StatusConflict,
						"debug":   "--------",
						"details": map[string]interface{}{},
						"id":      "string",
						"message": "error",
						"reason":  "error",
						"request": "d7ef54b1-ec15-46e6-bccb-524b82c035e6",
						"status":  "Conflict",
					},
				},
			)

			return nil, rr.Result(), fmt.Errorf("error")
		},
	)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).UpdateIdentity(ctx, credID, identityBody)

	if !reflect.DeepEqual(ids.Identities, make([]kClient.Identity, 0)) {
		t.Fatalf("expected identities to be empty not  %v", ids.Identities)
	}

	if ids.Error == nil {
		t.Fatal("expected ids.Error to be not nil")
	}

	if *ids.Error.Code != int64(http.StatusConflict) {
		t.Fatalf("expected code to be %v not  %v", http.StatusConflict, *ids.Error.Code)
	}

	if err == nil {
		t.Fatal("expected error to be not nil")
	}
}

func TestDeleteIdentitySuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()
	credID := "test-1"

	identityRequest := kClient.IdentityApiDeleteIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.DeleteIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().DeleteIdentity(ctx, credID).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().DeleteIdentityExecute(gomock.Any()).Times(1).Return(new(http.Response), nil)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).DeleteIdentity(ctx, credID)

	if len(ids.Identities) > 0 {
		t.Fatalf("invalid result, expected no identities, got %v", ids.Identities)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestDeleteIdentityFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockKratosIdentityApi := NewMockIdentityApi(ctrl)

	ctx := context.Background()
	credID := "test-1"

	identityRequest := kClient.IdentityApiDeleteIdentityRequest{
		ApiService: mockKratosIdentityApi,
	}

	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	mockTracer.EXPECT().Start(ctx, "kratos.IdentityApi.DeleteIdentity").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockKratosIdentityApi.EXPECT().DeleteIdentity(ctx, credID).Times(1).Return(identityRequest)
	mockKratosIdentityApi.EXPECT().DeleteIdentityExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r kClient.IdentityApiDeleteIdentityRequest) (*http.Response, error) {
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

			return rr.Result(), fmt.Errorf("error")
		},
	)

	ids, err := NewService(mockKratosIdentityApi, mockTracer, mockMonitor, mockLogger).DeleteIdentity(ctx, credID)

	if !reflect.DeepEqual(ids.Identities, make([]kClient.Identity, 0)) {
		t.Fatalf("expected identities to be empty not  %v", ids.Identities)
	}

	if ids.Error == nil {
		t.Fatal("expected ids.Error to be not nil")
	}

	if *ids.Error.Code != int64(http.StatusNotFound) {
		t.Fatalf("expected code to be %v not  %v", http.StatusNotFound, *ids.Error.Code)
	}

	if err == nil {
		t.Fatal("expected error to be not nil")
	}
}

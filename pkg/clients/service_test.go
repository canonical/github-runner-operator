package clients

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	reflect "reflect"
	"testing"

	"github.com/canonical/identity-platform-admin-ui/internal/monitoring"
	"github.com/golang/mock/gomock"
	hClient "github.com/ory/hydra-client-go/v2"
	"go.opentelemetry.io/otel/trace"
)

//go:generate mockgen -build_flags=--mod=mod -package clients -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package clients -destination ./mock_clients.go -source=./interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package clients -destination ./mock_monitor.go -source=../../internal/monitoring/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package clients -destination ./mock_tracing.go go.opentelemetry.io/otel/trace Tracer
//go:generate mockgen -build_flags=--mod=mod -package clients -destination ./mock_hydra.go github.com/ory/hydra-client-go/v2 OAuth2Api

func TestGetClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	const clientId = "client_id"

	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	clientReq := hClient.OAuth2ApiGetOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().GetOAuth2Client(gomock.Any(), clientId).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().GetOAuth2ClientExecute(gomock.Any()).Times(1).Return(c, new(http.Response), nil)
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.GetOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).GetClient(ctx, clientId)

	if resp.ServiceError != nil {
		t.Fatal("expected serviceError to be nil, got: ", resp.ServiceError)
	}
	if !reflect.DeepEqual(resp.Resp, c) {
		t.Fatalf("expected data to be %+v, got: %+v", c, resp.Resp)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetClientFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	const clientId = "client_id"

	errResp := hClient.NewErrorOAuth2()
	errResp.SetError("error")
	errResp.SetErrorDescription("Some error happened")
	clientReq := hClient.OAuth2ApiGetOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}
	errJson, _ := errResp.MarshalJSON()
	serviceResp := &http.Response{
		Body: io.NopCloser(bytes.NewBuffer(errJson)),
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().GetOAuth2Client(gomock.Any(), clientId).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().GetOAuth2ClientExecute(gomock.Any()).Times(1).Return(nil, serviceResp, fmt.Errorf("error"))
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.GetOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).GetClient(ctx, clientId)
	expectedError := new(ErrorOAuth2)
	expectedError.Error = *errResp.Error
	expectedError.ErrorDescription = *errResp.ErrorDescription

	if !reflect.DeepEqual(resp.ServiceError, expectedError) {
		t.Fatalf("expected data to be %+v, got: %+v", errResp, resp.ServiceError)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestDeleteClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	const clientId = "client_id"

	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	clientReq := hClient.OAuth2ApiDeleteOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().DeleteOAuth2Client(gomock.Any(), clientId).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().DeleteOAuth2ClientExecute(gomock.Any()).Times(1).Return(new(http.Response), nil)
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.DeleteOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).DeleteClient(ctx, clientId)

	if resp.ServiceError != nil {
		t.Fatal("expected serviceError to be nil, got: ", resp.ServiceError)
	}
	if resp.Resp != nil {
		t.Fatalf("expected data to be %+v, got: %+v", c, resp.Resp)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestDeleteClientFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	const clientId = "client_id"

	errResp := hClient.NewErrorOAuth2()
	errResp.SetError("error")
	errResp.SetErrorDescription("Some error happened")
	clientReq := hClient.OAuth2ApiDeleteOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}
	errJson, _ := errResp.MarshalJSON()
	serviceResp := &http.Response{
		Body:       io.NopCloser(bytes.NewBuffer(errJson)),
		StatusCode: 400,
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().DeleteOAuth2Client(gomock.Any(), clientId).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().DeleteOAuth2ClientExecute(gomock.Any()).Times(1).Return(serviceResp, fmt.Errorf("error"))
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.DeleteOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).DeleteClient(ctx, clientId)
	expectedError := new(ErrorOAuth2)
	expectedError.Error = *errResp.Error
	expectedError.ErrorDescription = *errResp.ErrorDescription
	expectedError.StatusCode = serviceResp.StatusCode

	if !reflect.DeepEqual(resp.ServiceError, expectedError) {
		t.Fatalf("expected data to be %+v, got: %+v", errResp, resp.ServiceError)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestCreateClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	c := hClient.NewOAuth2Client()
	clientReq := hClient.OAuth2ApiCreateOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().CreateOAuth2Client(gomock.Any()).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().CreateOAuth2ClientExecute(gomock.Any()).Times(1).Return(c, new(http.Response), nil)
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.CreateOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).CreateClient(ctx, c)

	if resp.ServiceError != nil {
		t.Fatal("expected serviceError to be nil, got: ", resp.ServiceError)
	}
	if !reflect.DeepEqual(resp.Resp, c) {
		t.Fatalf("expected data to be %+v, got: %+v", c, resp.Resp)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestCreateClientFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	c := hClient.NewOAuth2Client()
	errResp := hClient.NewErrorOAuth2()
	errResp.SetError("error")
	errResp.SetErrorDescription("Some error happened")
	clientReq := hClient.OAuth2ApiCreateOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}
	errJson, _ := errResp.MarshalJSON()
	serviceResp := &http.Response{
		Body:       io.NopCloser(bytes.NewBuffer(errJson)),
		StatusCode: 404,
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().CreateOAuth2Client(gomock.Any()).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().CreateOAuth2ClientExecute(gomock.Any()).Times(1).Return(nil, serviceResp, fmt.Errorf("error"))
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.CreateOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).CreateClient(ctx, c)
	expectedError := new(ErrorOAuth2)
	expectedError.Error = *errResp.Error
	expectedError.ErrorDescription = *errResp.ErrorDescription
	expectedError.StatusCode = serviceResp.StatusCode

	if !reflect.DeepEqual(resp.ServiceError, expectedError) {
		t.Fatalf("expected data to be %+v, got: %+v", errResp, resp.ServiceError)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestUpdateClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	const clientId = "client_id"
	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	clientReq := hClient.OAuth2ApiSetOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().SetOAuth2Client(gomock.Any(), clientId).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().SetOAuth2ClientExecute(gomock.Any()).Times(1).Return(c, new(http.Response), nil)
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.SetOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).UpdateClient(ctx, c)

	if resp.ServiceError != nil {
		t.Fatal("expected serviceError to be nil, got: ", resp.ServiceError)
	}
	if !reflect.DeepEqual(resp.Resp, c) {
		t.Fatalf("expected data to be %+v, got: %+v", c, resp.Resp)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestUpdateClientFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	const clientId = "client_id"
	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	errResp := hClient.NewErrorOAuth2()
	errResp.SetError("error")
	errResp.SetErrorDescription("Some error happened")
	clientReq := hClient.OAuth2ApiSetOAuth2ClientRequest{
		ApiService: mockHydraOAuth2Api,
	}
	errJson, _ := errResp.MarshalJSON()
	serviceResp := &http.Response{
		Body:       io.NopCloser(bytes.NewBuffer(errJson)),
		StatusCode: 404,
	}

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().SetOAuth2Client(gomock.Any(), clientId).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().SetOAuth2ClientExecute(gomock.Any()).Times(1).Return(nil, serviceResp, fmt.Errorf("error"))
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.SetOAuth2Client").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).UpdateClient(ctx, c)
	expectedError := new(ErrorOAuth2)
	expectedError.Error = *errResp.Error
	expectedError.ErrorDescription = *errResp.ErrorDescription
	expectedError.StatusCode = serviceResp.StatusCode

	if !reflect.DeepEqual(resp.ServiceError, expectedError) {
		t.Fatalf("expected data to be %+v, got: %+v", errResp, resp.ServiceError)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestListClientSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	const clientId = "client_id"
	c := hClient.NewOAuth2Client()
	c.SetClientId(clientId)
	cs := []OAuth2Client{*c}
	clientReq := hClient.OAuth2ApiListOAuth2ClientsRequest{
		ApiService: mockHydraOAuth2Api,
	}
	size := 10
	page := "10"
	listReq := NewListClientsRequest("", "", page, size)

	ctx := context.Background()
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.ListOAuth2Clients").Times(1).Return(nil, trace.SpanFromContext(ctx))
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().ListOAuth2Clients(gomock.Any()).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().ListOAuth2ClientsExecute(gomock.Any()).Times(1).DoAndReturn(
		func(r hClient.OAuth2ApiListOAuth2ClientsRequest) ([]OAuth2Client, *http.Response, error) {
			if _size := (*int)(reflect.ValueOf(r).FieldByName("pageSize").UnsafePointer()); *_size != size {
				t.Fatalf("expected id to be %v, got %v", size, *_size)
			}
			if _page := (*string)(reflect.ValueOf(r).FieldByName("pageToken").UnsafePointer()); *_page != page {
				t.Fatalf("expected id to be %s, got %s", page, *_page)
			}
			return cs, new(http.Response), nil
		},
	)

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).ListClients(ctx, listReq)

	if resp.ServiceError != nil {
		t.Fatal("expected serviceError to be nil, got: ", resp.ServiceError)
	}
	if !reflect.DeepEqual(resp.Resp, cs) {
		t.Fatalf("expected data to be %+v, got: %+v", cs, resp.Resp)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestListClientFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)
	mockHydraOAuth2Api := NewMockOAuth2Api(ctrl)

	errResp := hClient.NewErrorOAuth2()
	errResp.SetError("error")
	errResp.SetErrorDescription("Some error happened")
	clientReq := hClient.OAuth2ApiListOAuth2ClientsRequest{
		ApiService: mockHydraOAuth2Api,
	}
	errJson, _ := errResp.MarshalJSON()
	serviceResp := &http.Response{
		Body:       io.NopCloser(bytes.NewBuffer(errJson)),
		StatusCode: 404,
	}
	listReq := NewListClientsRequest("", "", "1", 10)

	ctx := context.Background()
	mockHydra.EXPECT().OAuth2Api().Times(1).Return(mockHydraOAuth2Api)
	mockHydraOAuth2Api.EXPECT().ListOAuth2Clients(gomock.Any()).Times(1).Return(clientReq)
	mockHydraOAuth2Api.EXPECT().ListOAuth2ClientsExecute(gomock.Any()).Times(1).Return(nil, serviceResp, fmt.Errorf("error"))
	mockTracer.EXPECT().Start(ctx, "hydra.OAuth2Api.ListOAuth2Clients").Times(1).Return(nil, trace.SpanFromContext(ctx))

	resp, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).ListClients(ctx, listReq)
	expectedError := new(ErrorOAuth2)
	expectedError.Error = *errResp.Error
	expectedError.ErrorDescription = *errResp.ErrorDescription
	expectedError.StatusCode = serviceResp.StatusCode

	if !reflect.DeepEqual(resp.ServiceError, expectedError) {
		t.Fatalf("expected data to be %+v, got: %+v", errResp, resp.ServiceError)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestUnmarshalClient(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)

	c := hClient.NewOAuth2Client()
	jsonBody, _ := c.MarshalJSON()

	cc, err := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).UnmarshalClient(jsonBody)
	if !reflect.DeepEqual(cc, c) {
		t.Fatalf("expected flow to be %+v not %+v", c, cc)
	}
	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestParseLinks(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)

	nextToken := "next_token"
	lastToken := "last_token"
	size := 10
	links := "<https://example/next?page_token=" + nextToken + "&page_size=" + fmt.Sprint(size) + ">; rel=\"next\",<https://example/last?page_token=" + lastToken + "&page_size=" + fmt.Sprint(size) + ">; rel=\"last\""

	l := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).parseLinks(links)
	expectedLinks := new(PaginationLinksMeta)
	expectedLinks.Next = PaginationMeta{nextToken, size}
	expectedLinks.Last = PaginationMeta{lastToken, size}

	if !reflect.DeepEqual(l, expectedLinks) {
		t.Fatalf("expected data to be %+v, got: %+v", expectedLinks, l)
	}
}

func TestParseServiceError(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockHydra := NewMockHydraClientInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := monitoring.NewMockMonitorInterface(ctrl)

	errorMsg := "error"
	errorDescription := "Some error happened"
	statusCode := 400
	errResp := hClient.NewErrorOAuth2()
	errResp.SetError(errorMsg)
	errResp.SetErrorDescription(errorDescription)
	errJson, _ := errResp.MarshalJSON()
	serviceResp := &http.Response{
		Body:       io.NopCloser(bytes.NewBuffer(errJson)),
		StatusCode: statusCode,
	}
	err, _ := NewService(mockHydra, mockTracer, mockMonitor, mockLogger).parseServiceError(serviceResp)

	if err.Error != errorMsg {
		t.Fatalf("expected error to be %+v, got: %+v", errorMsg, err.Error)
	}
	if err.ErrorDescription != errorDescription {
		t.Fatalf("expected error description to be %+v, got: %+v", errorDescription, err.ErrorDescription)
	}
	if err.StatusCode != statusCode {
		t.Fatalf("expected status code to be %+v, got: %+v", statusCode, err.StatusCode)
	}
}

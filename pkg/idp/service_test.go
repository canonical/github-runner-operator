package idp

import (
	"context"
	"encoding/json"
	"fmt"
	reflect "reflect"
	"testing"

	gomock "github.com/golang/mock/gomock"
	"go.opentelemetry.io/otel/trace"
	"gopkg.in/yaml.v3"
	v1 "k8s.io/api/core/v1"
	metaV1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_logger.go -source=../../internal/logging/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_interfaces.go -source=./interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_monitor.go -source=../../internal/monitoring/interfaces.go
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_tracing.go go.opentelemetry.io/otel/trace Tracer
//go:generate mockgen -build_flags=--mod=mod -package idp -destination ./mock_corev1.go k8s.io/client-go/kubernetes/typed/core/v1 CoreV1Interface,ConfigMapInterface

func TestListResourcesSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	mockTracer.EXPECT().Start(ctx, "idp.Service.ListResources").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).ListResources(ctx)

	if !reflect.DeepEqual(is, idps) {
		t.Fatalf("expected providers to be %v not  %v", idps, is)

	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestListResourcesSuccessButEmpty(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = ""

	mockTracer.EXPECT().Start(ctx, "idp.Service.ListResources").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).ListResources(ctx)

	if len(is) != 0 {
		t.Fatalf("expected providers to be empty not  %v", is)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestListResourcesFailsOnConfigMap(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

	mockTracer.EXPECT().Start(ctx, "idp.Service.ListResources").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(nil, fmt.Errorf("broken"))
	mockLogger.EXPECT().Error(gomock.Any()).Times(1)
	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).ListResources(ctx)

	if is != nil {
		t.Fatalf("expected result to be nil not  %v", is)

	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestListResourcesFailsOnMissingKey(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data["random"] = string(rawIdps)

	mockTracer.EXPECT().Start(ctx, "idp.Service.ListResources").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockLogger.EXPECT().Errorf(gomock.Any(), gomock.Any()).Times(1)
	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).ListResources(ctx)

	if is != nil {
		t.Fatalf("expected result to be nil not  %v", is)

	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetResourceSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	mockTracer.EXPECT().Start(ctx, "idp.Service.GetResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetResource(ctx, idps[0].ID)

	if !reflect.DeepEqual(is[0], idps[0]) {
		t.Fatalf("expected providers to be %v not  %v", idps[0], is)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetResourceNotfound(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	mockTracer.EXPECT().Start(ctx, "idp.Service.GetResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetResource(ctx, "fake")

	if len(is) != 0 {
		t.Fatalf("expected providers to be empty not  %v", is)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetResourceSuccessButEmpty(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = ""

	mockTracer.EXPECT().Start(ctx, "idp.Service.GetResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetResource(ctx, "fake")

	if len(is) != 0 {
		t.Fatalf("expected providers to be empty not  %v", is)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestGetResourceFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = ""

	mockTracer.EXPECT().Start(ctx, "idp.Service.GetResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).GetResource(ctx, "fake")

	if len(is) != 0 {
		t.Fatalf("expected providers to be empty not  %v", is)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestEditResourceSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	c := new(Configuration)
	c.ClientSecret = "secret-9"

	mockTracer.EXPECT().Start(ctx, "idp.Service.EditResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).EditResource(ctx, idps[0].ID, c)

	if is[0].ClientSecret != c.ClientSecret {
		t.Fatalf("expected provider secret to be %v not  %v", c.ClientSecret, is[0].ClientSecret)

	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestEditResourceNotfound(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	c := new(Configuration)
	c.ClientSecret = "secret-9"

	mockTracer.EXPECT().Start(ctx, "idp.Service.EditResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).EditResource(ctx, "fake", c)

	if len(is) != 0 {
		t.Fatalf("expected providers to be empty not  %v", is)
	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestEditResourceFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	c := new(Configuration)
	c.ClientSecret = "secret-9"

	mockTracer.EXPECT().Start(ctx, "idp.Service.EditResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).Return(cm, fmt.Errorf("error"))

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).EditResource(ctx, idps[0].ID, c)

	if is != nil {
		t.Fatalf("expected providers to be nil, not %v", is)
	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestCreateResourceSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "okta_347646e49b484037b83690b020f9f629"
	c.ClientID = "347646e4-9b48-4037-b836-90b020f9f629"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	mockTracer.EXPECT().Start(ctx, "idp.Service.CreateResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			i := make([]*Configuration, 0)

			rawIdps, _ := configMap.Data[cfg.KeyName]

			_ = yaml.Unmarshal([]byte(rawIdps), &i)

			if len(i) != len(idps)+1 {
				t.Fatalf("expected providers to be %v not %v", len(idps)+1, len(i))
			}
			return cm, nil
		},
	)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).CreateResource(ctx, c)

	if is == nil {
		t.Fatalf("expected provider to be not nil %v", is)
	}

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestCreateResourceFailsConflict(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "microsoft_af675f353bd7451588e2b8032e315f6f"
	c.ClientID = "af675f35-3bd7-4515-88e2-b8032e315f6f"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	mockTracer.EXPECT().Start(ctx, "idp.Service.CreateResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).CreateResource(ctx, c)

	if !reflect.DeepEqual(is, idps) {
		t.Fatalf("expected provider to be %v not %v", idps, is)
	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestCreateResourceFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	c := new(Configuration)
	c.ClientSecret = "secret-9"
	c.ID = "okta_347646e49b484037b83690b020f9f629"
	c.ClientID = "347646e4-9b48-4037-b836-90b020f9f629"
	c.Provider = "okta"
	c.Mapper = "file:///etc/config/kratos/okta_schema.jsonnet"
	c.Scope = []string{"email"}

	mockTracer.EXPECT().Start(ctx, "idp.Service.CreateResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			i := make([]*Configuration, 0)

			rawIdps, _ := configMap.Data[cfg.KeyName]

			_ = yaml.Unmarshal([]byte(rawIdps), &i)

			if len(i) != len(idps)+1 {
				t.Fatalf("expected providers to be %v not %v", len(idps)+1, len(i))
			}
			return nil, fmt.Errorf("error")
		},
	)

	is, err := NewService(cfg, mockTracer, mockMonitor, mockLogger).CreateResource(ctx, c)

	if is != nil {
		t.Fatalf("expected provider to be nil not %v", is)
	}

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

func TestDeleteResourceSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	mockTracer.EXPECT().Start(ctx, "idp.Service.DeleteResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(2).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)
	mockConfigMapV1.EXPECT().Update(gomock.Any(), cm, gomock.Any()).Times(1).DoAndReturn(
		func(ctx context.Context, configMap *v1.ConfigMap, opts metaV1.UpdateOptions) (*v1.ConfigMap, error) {
			i := make([]*Configuration, 0)

			rawIdps, _ := configMap.Data[cfg.KeyName]

			_ = yaml.Unmarshal([]byte(rawIdps), &i)

			if len(i) != len(idps)-1 {
				t.Fatalf("expected providers to be %v not %v", len(idps)+1, len(i))
			}
			return cm, nil
		},
	)

	err := NewService(cfg, mockTracer, mockMonitor, mockLogger).DeleteResource(ctx, idps[0].ID)

	if err != nil {
		t.Fatalf("expected error to be nil not  %v", err)
	}
}

func TestDeleteResourceFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mockLogger := NewMockLoggerInterface(ctrl)
	mockTracer := NewMockTracer(ctrl)
	mockMonitor := NewMockMonitorInterface(ctrl)
	mockCoreV1 := NewMockCoreV1Interface(ctrl)
	mockConfigMapV1 := NewMockConfigMapInterface(ctrl)
	ctx := context.Background()

	cfg := new(Config)
	cfg.K8s = mockCoreV1
	cfg.KeyName = "idps.yaml"
	cfg.Name = "idps"
	cfg.Namespace = "default"

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

	rawIdps, _ := json.Marshal(idps)
	cm := new(v1.ConfigMap)
	cm.Data = make(map[string]string)
	cm.Data[cfg.KeyName] = string(rawIdps)

	mockTracer.EXPECT().Start(ctx, "idp.Service.DeleteResource").Times(1).Return(ctx, trace.SpanFromContext(ctx))
	mockCoreV1.EXPECT().ConfigMaps(cfg.Namespace).Times(1).Return(mockConfigMapV1)
	mockConfigMapV1.EXPECT().Get(ctx, cfg.Name, gomock.Any()).Times(1).Return(cm, nil)

	err := NewService(cfg, mockTracer, mockMonitor, mockLogger).DeleteResource(ctx, "fake")

	if err == nil {
		t.Fatalf("expected error not to be nil")
	}
}

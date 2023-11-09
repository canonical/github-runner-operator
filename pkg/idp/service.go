package idp

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/canonical/identity-platform-admin-ui/internal/monitoring"
	"github.com/google/uuid"
	"go.opentelemetry.io/otel/trace"
	"gopkg.in/yaml.v3"
	metaV1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	coreV1 "k8s.io/client-go/kubernetes/typed/core/v1"
)

type Config struct {
	Name      string
	Namespace string
	KeyName   string
	K8s       coreV1.CoreV1Interface
}

type Service struct {
	cmName      string
	cmNamespace string
	keyName     string

	k8s coreV1.CoreV1Interface

	tracer  trace.Tracer
	monitor monitoring.MonitorInterface
	logger  logging.LoggerInterface
}

func (s *Service) ListResources(ctx context.Context) ([]*Configuration, error) {
	ctx, span := s.tracer.Start(ctx, "idp.Service.ListResources")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}

	return s.idpConfiguration(cm.Data), nil

}

func (s *Service) GetResource(ctx context.Context, providerID string) ([]*Configuration, error) {
	ctx, span := s.tracer.Start(ctx, "idp.Service.GetResource")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}

	idps := s.idpConfiguration(cm.Data)

	if idps == nil {
		return nil, nil
	}

	// TODO @shipperizer find a better way to index the idps
	for _, idp := range idps {
		if idp.ID == providerID {
			return []*Configuration{idp}, nil
		}
	}
	return []*Configuration{}, nil
}

func (s *Service) EditResource(ctx context.Context, providerID string, data *Configuration) ([]*Configuration, error) {
	ctx, span := s.tracer.Start(ctx, "idp.Service.EditResource")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}

	idps := s.idpConfiguration(cm.Data)

	if idps == nil {
		return nil, nil
	}

	var idp *Configuration
	// TODO @shipperizer find a better way to index the idps
	for _, i := range idps {
		if i.ID == providerID {
			i = s.mergeConfiguration(i, data)
			idp = i
		}
	}

	if idp == nil {
		return []*Configuration{}, fmt.Errorf("provider with ID %s not found", providerID)
	}

	rawIdps, err := json.Marshal(idps)

	if err != nil {
		return nil, err
	}

	cm.Data[s.keyName] = string(rawIdps)

	if _, err = s.k8s.ConfigMaps(s.cmNamespace).Update(ctx, cm, metaV1.UpdateOptions{}); err != nil {

		return nil, err
	}

	return []*Configuration{idp}, nil

}

func (s *Service) CreateResource(ctx context.Context, data *Configuration) ([]*Configuration, error) {
	ctx, span := s.tracer.Start(ctx, "idp.Service.CreateResource")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}

	idps := s.idpConfiguration(cm.Data)

	if idps == nil {
		return nil, nil
	}

	var idp *Configuration
	// TODO @shipperizer find a better way to index the idps
	for _, i := range idps {
		if i.ID == data.ID {
			return idps, fmt.Errorf("provider with same ID already exists")
		}
	}

	idps = append(idps, data)

	rawIdps, err := json.Marshal(idps)

	if err != nil {
		return nil, err
	}

	cm.Data[s.keyName] = string(rawIdps)

	if _, err = s.k8s.ConfigMaps(s.cmNamespace).Update(ctx, cm, metaV1.UpdateOptions{}); err != nil {

		return nil, err
	}

	return []*Configuration{idp}, nil
}

func (s *Service) DeleteResource(ctx context.Context, providerID string) error {
	ctx, span := s.tracer.Start(ctx, "idp.Service.DeleteResource")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return err
	}

	var found bool
	idps := s.idpConfiguration(cm.Data)

	if idps == nil {
		return nil
	}

	newIdps := make([]*Configuration, 0)

	// TODO @shipperizer find a better way to index the idps
	for _, i := range idps {

		if i.ID == providerID {
			found = true
		} else {
			newIdps = append(newIdps, i)
		}
	}

	if !found {
		return fmt.Errorf("provider with ID %s not found", providerID)
	}

	rawIdps, err := json.Marshal(newIdps)

	if err != nil {
		return err
	}

	cm.Data[s.keyName] = string(rawIdps)

	if _, err = s.k8s.ConfigMaps(s.cmNamespace).Update(ctx, cm, metaV1.UpdateOptions{}); err != nil {

		return err
	}

	return nil

}

// TODO @shipperizer ugly but safe, other way is to json/yaml Marshal/Unmarshal and use omitempty
func (s *Service) mergeConfiguration(base, update *Configuration) *Configuration {
	if update.Provider != "" {
		base.Provider = update.Provider
	}

	if update.Label != "" {
		base.Provider = update.Provider
	}

	if update.ClientID != "" {
		base.Provider = update.Provider
	}

	if update.ClientSecret != "" {
		base.ClientSecret = update.ClientSecret
	}

	if update.IssuerURL != "" {
		base.IssuerURL = update.IssuerURL
	}

	if update.AuthURL != "" {
		base.AuthURL = update.AuthURL
	}

	if update.TokenURL != "" {
		base.TokenURL = update.TokenURL
	}

	if update.Tenant != "" {
		base.Tenant = update.Tenant
	}

	if update.SubjectSource != "" {
		base.SubjectSource = update.SubjectSource
	}

	if update.TeamId != "" {
		base.TeamId = update.TeamId
	}

	if update.PrivateKeyId != "" {
		base.PrivateKeyId = update.PrivateKeyId
	}

	if update.PrivateKey != "" {
		base.PrivateKey = update.PrivateKey
	}

	if update.Scope != nil && len(update.Scope) > 0 {
		base.Scope = update.Scope
	}

	if update.Mapper != "" {
		base.Mapper = update.Mapper
	}

	if update.RequestedClaims != nil {
		base.RequestedClaims = update.RequestedClaims
	}

	return base
}

func (s *Service) idpConfiguration(idps map[string]string) []*Configuration {

	idpConfig := make([]*Configuration, 0)

	rawIdps, ok := idps[s.keyName]

	if !ok {
		s.logger.Errorf("failed to find key %s in configMap %v", s.keyName, idps)
		return nil
	}

	err := yaml.Unmarshal([]byte(rawIdps), &idpConfig)

	if err != nil {
		s.logger.Errorf("failed unmarshalling %s - %v", rawIdps, err)
		return nil
	}

	return idpConfig
}

func (s *Service) keyIDMapper(id, namespace string) string {
	return uuid.NewSHA1(uuid.Nil, []byte(fmt.Sprintf("%s.%s", id, namespace))).String()
}

// TODO @shipperizer analyze if providers IDs need to be what we use for path or if filename is the right one
func NewService(config *Config, tracer trace.Tracer, monitor monitoring.MonitorInterface, logger logging.LoggerInterface) *Service {
	s := new(Service)

	if config == nil {
		panic("empty config for IDP service")
	}

	s.k8s = config.K8s
	s.cmName = config.Name
	s.cmNamespace = config.Namespace
	// TODO @shipperizer fetch it from the config.KeyName
	s.keyName = "idps.yaml"

	s.monitor = monitor
	s.tracer = tracer
	s.logger = logger

	return s
}

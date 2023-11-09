package schemas

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/canonical/identity-platform-admin-ui/internal/monitoring"
	kClient "github.com/ory/kratos-client-go"
	"go.opentelemetry.io/otel/trace"
	metaV1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	coreV1 "k8s.io/client-go/kubernetes/typed/core/v1"
)

const DEFAULT_SCHEMA = "default.schema"

type Config struct {
	Name      string
	Namespace string
	K8s       coreV1.CoreV1Interface
	Kratos    kClient.IdentityApi
}

type IdentitySchemaData struct {
	IdentitySchemas []kClient.IdentitySchemaContainer
	Error           *kClient.GenericError
}

type DefaultSchema struct {
	ID string `json:"schema_id"`
}

// TODO @shipperizer verify during integration test if this is actually the format
type KratosError struct {
	Error *kClient.GenericError `json:"error,omitempty"`
}

type Service struct {
	cmName      string
	cmNamespace string

	k8s    coreV1.CoreV1Interface
	kratos kClient.IdentityApi

	tracer  trace.Tracer
	monitor monitoring.MonitorInterface
	logger  logging.LoggerInterface
}

func (s *Service) parseError(ctx context.Context, r *http.Response) *kClient.GenericError {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.parseError")
	defer span.End()

	gerr := KratosError{Error: kClient.NewGenericErrorWithDefaults()}

	defer r.Body.Close()
	body, _ := io.ReadAll(r.Body)

	if err := json.Unmarshal(body, &gerr); err != nil {
		gerr.Error.SetMessage("unable to parse kratos error response")
		gerr.Error.SetCode(http.StatusInternalServerError)
	}

	return gerr.Error
}

func (s *Service) ListSchemas(ctx context.Context, page, size int64) (*IdentitySchemaData, error) {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.ListSchemas")
	defer span.End()

	schemas, rr, err := s.kratos.ListIdentitySchemasExecute(
		s.kratos.ListIdentitySchemas(ctx).Page(page).PerPage(size),
	)

	data := new(IdentitySchemaData)

	if err != nil {
		s.logger.Error(err)
		data.Error = s.parseError(ctx, rr)
	}

	data.IdentitySchemas = schemas

	// TODO @shipperizer check if schemas is defaulting to empty slice inside kratos-client
	if data.IdentitySchemas == nil {
		data.IdentitySchemas = make([]kClient.IdentitySchemaContainer, 0)
	}

	return data, err
}

func (s *Service) GetSchema(ctx context.Context, ID string) (*IdentitySchemaData, error) {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.GetSchema")
	defer span.End()

	schema, rr, err := s.kratos.GetIdentitySchemaExecute(
		s.kratos.GetIdentitySchema(ctx, ID),
	)

	data := new(IdentitySchemaData)

	if err != nil {
		s.logger.Error(err)
		data.Error = s.parseError(ctx, rr)
	}

	if schema != nil {
		data.IdentitySchemas = []kClient.IdentitySchemaContainer{
			{Schema: schema, Id: &ID},
		}
	} else {
		data.IdentitySchemas = []kClient.IdentitySchemaContainer{}
	}

	return data, err
}

func (s *Service) EditSchema(ctx context.Context, ID string, data *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error) {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.EditSchema")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}

	i := new(IdentitySchemaData)

	// TODO @shipperizer DEFAULT_SCHEMA doesn't return here, but might be worth making it more explicit
	schemas := s.schemas(cm.Data)

	if _, ok := schemas[ID]; !ok {
		i.IdentitySchemas = []kClient.IdentitySchemaContainer{}

		return i, fmt.Errorf("schema with ID %s not found", ID)
	}

	rawSchema, err := json.Marshal(data.Schema)

	if err != nil {
		return nil, err
	}

	cm.Data[ID] = string(rawSchema)

	if _, err = s.k8s.ConfigMaps(s.cmNamespace).Update(ctx, cm, metaV1.UpdateOptions{}); err != nil {

		return nil, err
	}

	i.IdentitySchemas = []kClient.IdentitySchemaContainer{*data}

	return i, nil

}

func (s *Service) CreateSchema(ctx context.Context, data *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error) {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.CreateSchema")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}
	i := new(IdentitySchemaData)

	schemas := s.schemas(cm.Data)

	if _, ok := schemas[*data.Id]; ok {
		i.IdentitySchemas = []kClient.IdentitySchemaContainer{}

		return i, fmt.Errorf("schema with same ID already exists")
	}

	rawSchema, err := json.Marshal(data.Schema)

	if err != nil {
		return nil, err
	}

	cm.Data[*data.Id] = string(rawSchema)

	if _, err = s.k8s.ConfigMaps(s.cmNamespace).Update(ctx, cm, metaV1.UpdateOptions{}); err != nil {

		return nil, err
	}

	i.IdentitySchemas = []kClient.IdentitySchemaContainer{*data}

	return i, nil
}

func (s *Service) DeleteSchema(ctx context.Context, ID string) error {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.DeleteSchema")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return err
	}

	if ID == DEFAULT_SCHEMA {
		return fmt.Errorf("default schema %s cannot be deleted as ", ID)
	}

	if _, ok := cm.Data[ID]; !ok {
		return fmt.Errorf("schema with ID %s not found", ID)
	}

	delete(cm.Data, ID)

	if _, err = s.k8s.ConfigMaps(s.cmNamespace).Update(ctx, cm, metaV1.UpdateOptions{}); err != nil {

		return err
	}

	return nil

}

func (s *Service) GetDefaultSchema(ctx context.Context) (*DefaultSchema, error) {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.GetDefaultSchema")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}

	ID, ok := cm.Data[DEFAULT_SCHEMA]

	if !ok {
		return nil, fmt.Errorf("default schema %s missing", DEFAULT_SCHEMA)
	}

	defaultSchema := new(DefaultSchema)
	defaultSchema.ID = ID

	return defaultSchema, nil
}

func (s *Service) UpdateDefaultSchema(ctx context.Context, schemaID *DefaultSchema) (*DefaultSchema, error) {
	ctx, span := s.tracer.Start(ctx, "schemas.Service.UpdateDefaultSchema")
	defer span.End()

	cm, err := s.k8s.ConfigMaps(s.cmNamespace).Get(ctx, s.cmName, metaV1.GetOptions{})

	if err != nil {
		s.logger.Error(err.Error())
		return nil, err
	}

	if _, ok := cm.Data[schemaID.ID]; !ok || schemaID.ID == DEFAULT_SCHEMA {
		return nil, fmt.Errorf("schema with ID %s not available", schemaID.ID)
	}

	cm.Data[DEFAULT_SCHEMA] = schemaID.ID

	if _, err = s.k8s.ConfigMaps(s.cmNamespace).Update(ctx, cm, metaV1.UpdateOptions{}); err != nil {
		return nil, err
	}

	return schemaID, nil
}

func (s *Service) schemas(schemas map[string]string) map[string]*kClient.IdentitySchemaContainer {

	schemaConfig := make(map[string]*kClient.IdentitySchemaContainer)

	for key, rawSchema := range schemas {
		// skip if special key
		if key == DEFAULT_SCHEMA {
			continue
		}

		schema := make(map[string]interface{})

		err := json.Unmarshal([]byte(rawSchema), &schema)

		if err != nil {
			s.logger.Errorf("failed unmarshalling %s - %v", rawSchema, err)
			return nil
		}

		schemaConfig[key] = &kClient.IdentitySchemaContainer{Id: &key, Schema: schema}
	}

	return schemaConfig
}

// TODO @shipperizer analyze if providers IDs need to be what we use for path or if filename is the right one
func NewService(config *Config, tracer trace.Tracer, monitor monitoring.MonitorInterface, logger logging.LoggerInterface) *Service {
	s := new(Service)

	if config == nil {
		panic("empty config for schemas service")
	}

	s.kratos = config.Kratos
	s.k8s = config.K8s
	s.cmName = config.Name
	s.cmNamespace = config.Namespace

	s.monitor = monitor
	s.tracer = tracer
	s.logger = logger

	return s
}

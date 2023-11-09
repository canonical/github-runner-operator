package schemas

import (
	"context"

	kClient "github.com/ory/kratos-client-go"
)

type ServiceInterface interface {
	ListSchemas(context.Context, int64, int64) (*IdentitySchemaData, error)
	GetSchema(context.Context, string) (*IdentitySchemaData, error)
	EditSchema(context.Context, string, *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error)
	CreateSchema(context.Context, *kClient.IdentitySchemaContainer) (*IdentitySchemaData, error)
	DeleteSchema(context.Context, string) error
	GetDefaultSchema(context.Context) (*DefaultSchema, error)
	UpdateDefaultSchema(context.Context, *DefaultSchema) (*DefaultSchema, error)
}

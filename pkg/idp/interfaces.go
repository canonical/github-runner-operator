package idp

import (
	"context"
)

type ServiceInterface interface {
	ListResources(context.Context) ([]*Configuration, error)
	GetResource(context.Context, string) ([]*Configuration, error)
	EditResource(context.Context, string, *Configuration) ([]*Configuration, error)
	CreateResource(context.Context, *Configuration) ([]*Configuration, error)
	DeleteResource(context.Context, string) error
}

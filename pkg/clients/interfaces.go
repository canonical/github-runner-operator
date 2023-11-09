package clients

import (
	"context"

	hClient "github.com/ory/hydra-client-go/v2"
)

type HydraClientInterface interface {
	OAuth2Api() hClient.OAuth2Api
}

type OAuth2Client = hClient.OAuth2Client

type ServiceInterface interface {
	GetClient(context.Context, string) (*ServiceResponse, error)
	CreateClient(context.Context, *hClient.OAuth2Client) (*ServiceResponse, error)
	UpdateClient(context.Context, *hClient.OAuth2Client) (*ServiceResponse, error)
	ListClients(context.Context, *ListClientsRequest) (*ServiceResponse, error)
	DeleteClient(context.Context, string) (*ServiceResponse, error)
	UnmarshalClient(data []byte) (*hClient.OAuth2Client, error)
}

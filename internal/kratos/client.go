package kratos

import (
	"net/http"

	client "github.com/ory/kratos-client-go"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

type Client struct {
	c *client.APIClient
}

func (c *Client) IdentityApi() client.IdentityApi {
	return c.c.IdentityApi
}

func NewClient(url string, debug bool) *Client {
	c := new(Client)

	configuration := client.NewConfiguration()
	configuration.Debug = debug
	configuration.Servers = []client.ServerConfiguration{
		{
			URL: url,
		},
	}

	configuration.HTTPClient = new(http.Client)
	configuration.HTTPClient.Transport = otelhttp.NewTransport(http.DefaultTransport)

	c.c = client.NewAPIClient(configuration)

	return c
}

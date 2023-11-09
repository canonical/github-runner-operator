package idp

import "encoding/json"

// TODO @shipperizer once import of library is fixed find a way to use this schema with extra yaml annotations
// coming from https://pkg.go.dev/github.com/ory/kratos@v1.0.0/selfservice/strategy/oidc#Configuration
// importing the library github.com/ory/kratos fails due to compilations on their side
type Configuration struct {
	// ID is the provider's ID
	ID string `json:"id" yaml:"id"`

	// Provider is either "generic" for a generic OAuth 2.0 / OpenID Connect Provider or one of:
	// - generic
	// - google
	// - github
	// - github-app
	// - gitlab
	// - microsoft
	// - discord
	// - slack
	// - facebook
	// - auth0
	// - vk
	// - yandex
	// - apple
	// - spotify
	// - netid
	// - dingtalk
	// - linkedin
	// - patreon
	Provider string `json:"provider" yaml:"provider"`

	// Label represents an optional label which can be used in the UI generation.
	Label string `json:"label"`

	// ClientID is the application's Client ID.
	ClientID string `json:"client_id" yaml:"client_id"`

	// ClientSecret is the application's secret.
	ClientSecret string `json:"client_secret" yaml:"client_secret"`

	// IssuerURL is the OpenID Connect Server URL. You can leave this empty if `provider` is not set to `generic`.
	// If set, neither `auth_url` nor `token_url` are required.
	IssuerURL string `json:"issuer_url" yaml:"issuer_url"`

	// AuthURL is the authorize url, typically something like: https://example.org/oauth2/auth
	// Should only be used when the OAuth2 / OpenID Connect server is not supporting OpenID Connect Discovery and when
	// `provider` is set to `generic`.
	AuthURL string `json:"auth_url" yaml:"auth_url"`

	// TokenURL is the token url, typically something like: https://example.org/oauth2/token
	// Should only be used when the OAuth2 / OpenID Connect server is not supporting OpenID Connect Discovery and when
	// `provider` is set to `generic`.
	TokenURL string `json:"token_url" yaml:"token_url"`

	// Tenant is the Azure AD Tenant to use for authentication, and must be set when `provider` is set to `microsoft`.
	// Can be either `common`, `organizations`, `consumers` for a multitenant application or a specific tenant like
	// `8eaef023-2b34-4da1-9baa-8bc8c9d6a490` or `contoso.onmicrosoft.com`.
	Tenant string `json:"microsoft_tenant" yaml:"microsoft_tenant"`

	// SubjectSource is a flag which controls from which endpoint the subject identifier is taken by microsoft provider.
	// Can be either `userinfo` or `me`.
	// If the value is `uerinfo` then the subject identifier is taken from sub field of uderifo standard endpoint response.
	// If the value is `me` then the `id` field of https://graph.microsoft.com/v1.0/me response is taken as subject.
	// The default is `userinfo`.
	SubjectSource string `json:"subject_source" yaml:"subject_source"`

	// TeamId is the Apple Developer Team ID that's needed for the `apple` `provider` to work.
	// It can be found Apple Developer website and combined with `apple_private_key` and `apple_private_key_id`
	// is used to generate `client_secret`
	TeamId string `json:"apple_team_id" yaml:"apple_team_id"`

	// PrivateKeyId is the private Apple key identifier. Keys can be generated via developer.apple.com.
	// This key should be generated with the `Sign In with Apple` option checked.
	// This is needed when `provider` is set to `apple`
	PrivateKeyId string `json:"apple_private_key_id" yaml:"apple_private_key_id"`

	// PrivateKeyId is the Apple private key identifier that can be downloaded during key generation.
	// This is needed when `provider` is set to `apple`
	PrivateKey string `json:"apple_private_key" yaml:"apple_private_key"`

	// Scope specifies optional requested permissions.
	Scope []string `json:"scope" yaml:"scope"`

	// Mapper specifies the JSONNet code snippet which uses the OpenID Connect Provider's data (e.g. GitHub or Google
	// profile information) to hydrate the identity's data.
	//
	// It can be either a URL (file://, http(s)://, base64://) or an inline JSONNet code snippet.
	Mapper string `json:"mapper_url" yaml:"mapper_url"`

	// RequestedClaims string encoded json object that specifies claims and optionally their properties which should be
	// included in the id_token or returned from the UserInfo Endpoint.
	//
	// More information: https://openid.net/specs/openid-connect-core-1_0.html#ClaimsParameter
	RequestedClaims json.RawMessage `json:"requested_claims" yaml:"requested_claims"`
}

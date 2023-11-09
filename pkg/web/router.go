package web

import (
	"net/http"

	ih "github.com/canonical/identity-platform-admin-ui/internal/hydra"
	ik "github.com/canonical/identity-platform-admin-ui/internal/kratos"
	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/canonical/identity-platform-admin-ui/internal/monitoring"
	"github.com/canonical/identity-platform-admin-ui/internal/tracing"
	chi "github.com/go-chi/chi/v5"
	middleware "github.com/go-chi/chi/v5/middleware"
	trace "go.opentelemetry.io/otel/trace"

	"github.com/canonical/identity-platform-admin-ui/pkg/clients"
	"github.com/canonical/identity-platform-admin-ui/pkg/identities"
	"github.com/canonical/identity-platform-admin-ui/pkg/idp"
	"github.com/canonical/identity-platform-admin-ui/pkg/metrics"
	"github.com/canonical/identity-platform-admin-ui/pkg/schemas"
	"github.com/canonical/identity-platform-admin-ui/pkg/status"
)

func NewRouter(idpConfig *idp.Config, schemasConfig *schemas.Config, hydraClient *ih.Client, kratos *ik.Client, tracer trace.Tracer, monitor monitoring.MonitorInterface, logger logging.LoggerInterface) http.Handler {
	router := chi.NewMux()

	middlewares := make(chi.Middlewares, 0)
	middlewares = append(
		middlewares,
		middleware.RequestID,
		monitoring.NewMiddleware(monitor, logger).ResponseTime(),
		middlewareCORS([]string{"*"}),
	)

	// TODO @shipperizer add a proper configuration to enable http logger middleware as it's expensive
	if true {
		middlewares = append(
			middlewares,
			middleware.RequestLogger(logging.NewLogFormatter(logger)), // LogFormatter will only work if logger is set to DEBUG level
		)
	}

	router.Use(middlewares...)

	status.NewAPI(tracer, monitor, logger).RegisterEndpoints(router)
	metrics.NewAPI(logger).RegisterEndpoints(router)
	identities.NewAPI(
		identities.NewService(kratos.IdentityApi(), tracer, monitor, logger),
		logger,
	).RegisterEndpoints(router)
	clients.NewAPI(
		clients.NewService(hydraClient, tracer, monitor, logger),
		logger,
	).RegisterEndpoints(router)
	idp.NewAPI(
		idp.NewService(idpConfig, tracer, monitor, logger),
		logger,
	).RegisterEndpoints(router)
	schemas.NewAPI(
		schemas.NewService(schemasConfig, tracer, monitor, logger),
		logger,
	).RegisterEndpoints(router)
	return tracing.NewMiddleware(monitor, logger).OpenTelemetry(router)
}

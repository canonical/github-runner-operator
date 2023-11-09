package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"

	"syscall"
	"time"

	ih "github.com/canonical/identity-platform-admin-ui/internal/hydra"
	"github.com/canonical/identity-platform-admin-ui/internal/k8s"
	"github.com/kelseyhightower/envconfig"

	"github.com/canonical/identity-platform-admin-ui/internal/config"
	ik "github.com/canonical/identity-platform-admin-ui/internal/kratos"
	"github.com/canonical/identity-platform-admin-ui/internal/logging"
	"github.com/canonical/identity-platform-admin-ui/internal/monitoring/prometheus"
	"github.com/canonical/identity-platform-admin-ui/internal/tracing"
	"github.com/canonical/identity-platform-admin-ui/internal/version"
	"github.com/canonical/identity-platform-admin-ui/pkg/idp"
	"github.com/canonical/identity-platform-admin-ui/pkg/schemas"
	"github.com/canonical/identity-platform-admin-ui/pkg/web"
)

func main() {

	specs := new(config.EnvSpec)

	if err := envconfig.Process("", specs); err != nil {
		panic(fmt.Errorf("issues with environment sourcing: %s", err))
	}

	flags := config.NewFlags()

	switch {
	case flags.ShowVersion:
		fmt.Printf("App Version: %s\n", version.Version)
		os.Exit(0)
	default:
		break
	}

	logger := logging.NewLogger(specs.LogLevel, specs.LogFile)

	monitor := prometheus.NewMonitor("identity-admin-ui", logger)
	tracer := tracing.NewTracer(tracing.NewConfig(specs.TracingEnabled, specs.OtelGRPCEndpoint, specs.OtelHTTPEndpoint, logger))

	hAdminClient := ih.NewClient(specs.HydraAdminURL, specs.Debug)
	kAdminClient := ik.NewClient(specs.KratosAdminURL, specs.Debug)
	kPublicClient := ik.NewClient(specs.KratosPublicURL, specs.Debug)

	k8sCoreV1, err := k8s.NewCoreV1Client()

	if err != nil {
		panic(err)
	}

	idpConfig := &idp.Config{
		K8s:       k8sCoreV1,
		Name:      specs.IDPConfigMapName,
		Namespace: specs.IDPConfigMapNamespace,
	}

	schemasConfig := &schemas.Config{
		K8s:       k8sCoreV1,
		Kratos:    kPublicClient.IdentityApi(),
		Name:      specs.SchemasConfigMapName,
		Namespace: specs.SchemasConfigMapNamespace,
	}
	router := web.NewRouter(idpConfig, schemasConfig, hAdminClient, kAdminClient, tracer, monitor, logger)

	logger.Infof("Starting server on port %v", specs.Port)

	srv := &http.Server{
		Addr:         fmt.Sprintf("0.0.0.0:%v", specs.Port),
		WriteTimeout: time.Second * 15,
		ReadTimeout:  time.Second * 15,
		IdleTimeout:  time.Second * 60,
		Handler:      router,
	}

	go func() {
		if err := srv.ListenAndServe(); err != nil {
			logger.Fatal(err)
		}
	}()

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	// Block until we receive our signal.
	<-c

	// Create a deadline to wait for.
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	// Doesn't block if no connections, but will otherwise wait
	// until the timeout deadline.
	srv.Shutdown(ctx)

	logger.Desugar().Sync()

	// Optionally, you could run srv.Shutdown in a goroutine and block on
	// <-ctx.Done() if your application should wait for other services
	// to finalize based on context cancellation.
	logger.Info("Shutting down")
	os.Exit(0)

}

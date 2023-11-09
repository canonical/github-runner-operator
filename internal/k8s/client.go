package k8s

import (
	"k8s.io/client-go/kubernetes"
	coreV1 "k8s.io/client-go/kubernetes/typed/core/v1"
	"k8s.io/client-go/rest"
)

func NewCoreV1Client() (coreV1.CoreV1Interface, error) {
	// httpClient := new(http.Client)
	// httpClient.Transport = otelhttp.NewTransport(http.DefaultTransport)

	// creates the in-cluster config
	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, err
	}

	// creates the clientset
	// clientset, err := kubernetes.NewForConfigAndClient(config, httpClient)
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, err
	}

	return clientset.CoreV1(), nil
}

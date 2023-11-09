# Changelog

## [1.2.0](https://github.com/canonical/identity-platform-admin-ui/compare/v1.1.0...v1.2.0) (2023-08-10)


### Features

* add idp handlers ([405bad3](https://github.com/canonical/identity-platform-admin-ui/commit/405bad314cb3b3a79b0455b74b7a123cb09818b7))
* add idp service ([4f04546](https://github.com/canonical/identity-platform-admin-ui/commit/4f04546e2a1f75f16ce36a1bea051ce012d8e44c))
* wire up main and router with new dependencies ([7c218d3](https://github.com/canonical/identity-platform-admin-ui/commit/7c218d3ea8fd9413e808afa7f54a265a3e1dec6d))


### Bug Fixes

* add otel tracing to hydra client ([64871cd](https://github.com/canonical/identity-platform-admin-ui/commit/64871cdb232a92ebb11b4ed0d05282898cdc9f9d))
* create k8s coreV1 package ([ff260f9](https://github.com/canonical/identity-platform-admin-ui/commit/ff260f927d1930fb587ac515962fe4605b2d9223))
* drop unused const ([bb3bd28](https://github.com/canonical/identity-platform-admin-ui/commit/bb3bd28a0f1df6904d5f6355b9bcc198276d8db7))
* use io pkg instead of ioutil ([909459c](https://github.com/canonical/identity-platform-admin-ui/commit/909459c1041391d6906e20ecbe9c129523c8774f))
* use new instead of & syntax ([9908ddc](https://github.com/canonical/identity-platform-admin-ui/commit/9908ddc30301816b623d0bf8e064cae1c1dd91f6))

## [1.1.0](https://github.com/canonical/identity-platform-admin-ui/compare/v1.0.0...v1.1.0) (2023-07-27)


### Features

* add hydra service ([17a3c86](https://github.com/canonical/identity-platform-admin-ui/commit/17a3c866cffcf5ef8c5f54881482ccfe2f4b4d1d))
* add identities service layer ([d619daf](https://github.com/canonical/identity-platform-admin-ui/commit/d619dafe04f3452402f488a4f75739cfdc68b2d5))
* create apis for identities kratos REST endpoints ([6da5dae](https://github.com/canonical/identity-platform-admin-ui/commit/6da5dae6f73602c80057ed20b2de7bdb06288fcb))
* create kratos client ([d009507](https://github.com/canonical/identity-platform-admin-ui/commit/d009507359360bbd1fa05b494e5db25d68721d77))


### Bug Fixes

* add jaeger propagator as ory components support only these spans for now ([5a90f83](https://github.com/canonical/identity-platform-admin-ui/commit/5a90f838f224add360c81aeaf88a66e2811a7185))
* fail if HYDRA_ADMIN_URL is not provided ([c9e1844](https://github.com/canonical/identity-platform-admin-ui/commit/c9e18449a2cef297ed34414ec1a5b88177ce9b38))
* IAM-339 - add generic response pkg ([b98a505](https://github.com/canonical/identity-platform-admin-ui/commit/b98a505ac3ababddb27a0b903842db4f73a65e1d))
* introduce otelHTTP and otelGRPC exporter for tempo ([9156892](https://github.com/canonical/identity-platform-admin-ui/commit/91568926bc441372c4b342a5cdd42433b6fbd3fb))
* only print hydra debug logs on debug ([15dc2b4](https://github.com/canonical/identity-platform-admin-ui/commit/15dc2b4ba473384569b13fcbc84ecb29cfb021d4))
* wire up new kratos endpoints ([1d881a7](https://github.com/canonical/identity-platform-admin-ui/commit/1d881a70ddfed165ba85017d517f56e9e7b2c490))

## 1.0.0 (2023-07-07)


### Features

* Add go code skeleton ([10aec9d](https://github.com/canonical/identity-platform-admin-ui/commit/10aec9d8f2181d7c6c0d5cc2aebf861381827139))
* add ui skeleton ([ce6b51f](https://github.com/canonical/identity-platform-admin-ui/commit/ce6b51ff0659c16751b7d2371d4b19f399cad59a))

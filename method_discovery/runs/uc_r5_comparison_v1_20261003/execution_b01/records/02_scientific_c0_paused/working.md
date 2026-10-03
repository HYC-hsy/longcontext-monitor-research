Both spec violations fixed (deprecated.go 2-param signatures, keys.go "Hessian2"). Agent now fixing extensive cascading compatibility from deprecated.go reversion: tracing.go, stream_middleware.go, client/server stream.go need reversion to 2-param to match deprecated API.

At next completion, verify: spec violations remain fixed, cascading changes consistent, Target 6 implementations correct, builds succeed.

Awaiting completion of cascading fixes and next completion proposal.

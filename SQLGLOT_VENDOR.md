# Vendored SQLGlot

This repository includes the complete runtime source package of SQLGlot
version 26.3.0 under `sqlglot/`.

The source was obtained from the `sqlglot==26.3.0` source distribution. The
application imports this repository copy directly, so SQLGlot does not need to
be installed separately at runtime.

SQLGlot is distributed under the MIT License. The upstream license is copied
to [SQLGLOT_LICENSE](SQLGLOT_LICENSE).

The vendored package is retained as an educational reference for the
transpilation pipeline. The application-specific orchestration is implemented
outside the vendored package.

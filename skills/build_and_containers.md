# Build Systems & Container Heuristics

Identify the build system before selecting commands. Use focused verification over full builds where possible.

## Detection & Execution
* **Maven:** Look for `pom.xml` / `mvnw`. Prefer wrapper: `./mvnw package`
* **Gradle:** Look for `build.gradle` / `gradlew`. Prefer wrapper: `./gradlew assemble`
* **Node/npm:** Look for `package.json`. Use `npm ci` for CI installs; respect existing scripts.
* **Nx:** Look for `nx.json` / `project.json`. Use affected commands: `npx nx affected -t build`

## Docker Heuristics
1. Inspect `.dockerignore`.
2. Determine if the Dockerfile builds the app or copies a prebuilt artifact.
3. Prefer multi-stage builds and immutable base images (`@sha256:digest`).
4. Do not copy secrets into images.

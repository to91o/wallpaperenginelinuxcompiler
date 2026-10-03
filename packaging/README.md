# GitHub Packages

Two independent file-distribution packages are published to GHCR and linked to this repository:

- `ghcr.io/to91o/plasma-video-wallpaper:v0.1.0-alpha.3`
- `ghcr.io/to91o/wallpaper-engine-to-mp4:v0.1.0-alpha.3`

These OCI packages contain release files under `/package`. They are **not runnable desktop containers** or DEB packages. Release ZIP downloads are recommended for normal installation. Original wallpaper assets and installed Python dependencies are not bundled.

With Docker available, extract a package without executing its contents:

```bash
docker pull ghcr.io/to91o/plasma-video-wallpaper:v0.1.0-alpha.3
docker create --name plasma-wallpaper-files ghcr.io/to91o/plasma-video-wallpaper:v0.1.0-alpha.3 /unused
mkdir plasma-video-wallpaper
docker cp plasma-wallpaper-files:/package/. ./plasma-video-wallpaper/
docker rm plasma-wallpaper-files
cd plasma-video-wallpaper
bash install.sh
```

For the converter, substitute its package name, use a distinct temporary container/folder, and follow the extracted README. Private packages require registry login before pulling.

The publish workflow runs on release tag pushes or can be manually dispatched with an existing release tag. It verifies file contents before uploading, uses repository-scoped GitHub Actions authentication, and labels packages with their repository URL. New GHCR packages may default to private: the owner can set each package to public in **Package settings → Change visibility**. Repository visibility alone does not prove package visibility.

# File distribution package only: no OS, executable entrypoint or desktop runtime.
FROM scratch
COPY . /package/

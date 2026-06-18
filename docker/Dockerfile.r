# Coala R executor — Bioconductor official Docker image (R + Bioc preconfigured).
# Base tag RELEASE_3_23 ships linux/amd64 and linux/arm64 (Apple Silicon).
#
# Override at build time, e.g.:
#   docker build --build-arg BIOC_DOCKER_TAG=RELEASE_3_22 -f docker/Dockerfile.r .
ARG BIOC_DOCKER_TAG=RELEASE_3_23
FROM bioconductor/bioconductor_docker:${BIOC_DOCKER_TAG}

# Coala mount points
RUN mkdir -p /workspace /input /output

WORKDIR /workspace

# tidyverse via BiocManager (uses prebuilt binaries from the Bioconductor/CRAN stack in this image)
RUN Rscript -e "BiocManager::install('tidyverse', ask = FALSE, update = FALSE)"

CMD ["Rscript"]

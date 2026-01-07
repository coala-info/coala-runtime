# R executor image with r2u, bioc2u, and tidyverse
FROM rocker/r2u:latest

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    R_HOME=/usr/lib/R

# Install BiocManager (needed for Bioconductor package installation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    r-cran-biocmanager \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure BiocManager to use the latest stable version
# This will be used when installing Bioconductor packages at runtime
RUN Rscript -e "BiocManager::install(version = '3.22', ask = FALSE, update = FALSE)" || true

# Note: bioc2u repository setup
# bioc2u provides Bioconductor packages as Ubuntu binaries
# If available, it can be added as a repository, but BiocManager::install()
# will work for installing Bioconductor packages at runtime
# The rocker/r2u base image already has bspm configured for CRAN packages

# Install default R package (tidyverse) via apt (r2u provides binaries)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    r-cran-tidyverse \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create workspace directories
RUN mkdir -p /workspace /input /output

# Set working directory
WORKDIR /workspace

# Configure R to use bspm for automatic apt integration
# This ensures install.packages() uses apt when available
RUN echo "suppressMessages(bspm::enable())" >> ${R_HOME}/etc/Rprofile.site && \
    echo "options(bspm.version.check=FALSE)" >> ${R_HOME}/etc/Rprofile.site

# Default command (can be overridden)
CMD ["Rscript"]

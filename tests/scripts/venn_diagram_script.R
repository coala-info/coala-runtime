# Test script for creating a Venn diagram using VennDiagram package
# This script generates a Venn diagram showing two overlapping sets

library(VennDiagram);

# Create Venn diagram and save to PNG
output_path <- "/output/venn_diagram.png"
png(output_path, width = 800, height = 600, res = 150)
vd <- VennDiagram::venn.diagram(
    list(A = 1:150, B = 121:170), 
    filename = NULL,
    fill = c("lightblue", "lightgreen"),
    alpha = 0.5,
    cex = 1.5,
    fontfamily = "serif",
    cat.cex = 1.2,
    cat.fontfamily = "serif"
);
grid::grid.draw(vd);
dev.off();

cat("Venn diagram saved to:", output_path, "\n");
cat("Diagram shows sets A (1-150) and B (121-170) with overlap\n");

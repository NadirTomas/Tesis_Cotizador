import { WarningAmber } from "@mui/icons-material";
import { Alert, Box, FormControl, InputLabel, MenuItem, Select, TextField, Tooltip, Typography, Button } from "@mui/material";
import { useEffect, useState } from "react";

import type { Material } from "../services/materials";
import type { Piece } from "../services/pieces";
import { createQuotationItem } from "../services/quotations";

interface AddQuotationItemFormProps {
  quotationId: number;
  pieces: Piece[];
  materials: Material[];
  onItemAdded: () => void;
  /** Se dispara cada vez que cambia la pieza/material seleccionados -- para
   * que el padre pueda reaccionar (ej. pedir una recomendación de stock)
   * sin tener que duplicar este estado. */
  onSelectionChange?: (pieceId: number | "", materialId: number | "") => void;
}

/** Formulario para agregar un ítem a una cotización draft -- compartido
 * entre el wizard de creación y el detalle de cotización (antes duplicado
 * casi al pie de la letra entre ambos). */
function AddQuotationItemForm({ quotationId, pieces, materials, onItemAdded, onSelectionChange }: AddQuotationItemFormProps) {
  const [pieceId, setPieceId] = useState<number | "">("");
  const [materialId, setMaterialId] = useState<number | "">("");
  const [quantity, setQuantity] = useState(1);
  const [margin, setMargin] = useState(20);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onSelectionChange?.(pieceId, materialId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pieceId, materialId]);

  function handlePieceChange(id: number | "") {
    setPieceId(id);
    if (id !== "") {
      const piece = pieces.find((p) => p.id === id);
      if (piece?.material_id) setMaterialId(piece.material_id);
    }
  }

  async function handleAdd() {
    if (pieceId === "" || materialId === "") return;
    setAdding(true);
    setError(null);
    try {
      await createQuotationItem({
        quotation_id: quotationId,
        piece_id: pieceId as number,
        material_id: materialId as number,
        quantity,
        margin_percent: margin,
      });
      onItemAdded();
      setPieceId("");
      setMaterialId("");
      setQuantity(1);
      setMargin(20);
    } catch {
      setError("Error al agregar la pieza. Verificá que el material tenga configuración de máquina.");
    } finally {
      setAdding(false);
    }
  }

  const selectedPiece = pieces.find((p) => p.id === pieceId);

  return (
    <Box>
      <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.8rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 2 }}>
        Agregar pieza
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box display="flex" flexWrap="wrap" gap={2} alignItems="flex-start">
        <FormControl sx={{ minWidth: 220 }} required>
          <InputLabel>Pieza</InputLabel>
          <Select label="Pieza" value={pieceId} onChange={(e) => handlePieceChange(e.target.value as number | "")}>
            {pieces.map((p) => (
              <MenuItem key={p.id} value={p.id}>
                <Box display="flex" alignItems="center" gap={1}>
                  {p.name}
                  {p.length_cut_mm == null && (
                    <Tooltip title="Sin DXF — costos serán 0">
                      <WarningAmber fontSize="small" color="warning" />
                    </Tooltip>
                  )}
                </Box>
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl sx={{ minWidth: 200 }} required>
          <InputLabel>Material</InputLabel>
          <Select label="Material" value={materialId} onChange={(e) => setMaterialId(e.target.value as number | "")}>
            {materials.map((m) => (
              <MenuItem key={m.id} value={m.id}>{m.name} — {m.thickness_mm}mm</MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField label="Cantidad" type="number" value={quantity} onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))} sx={{ width: 100 }} inputProps={{ min: 1 }} />
        <TextField label="Margen %" type="number" value={margin} onChange={(e) => setMargin(parseFloat(e.target.value) || 0)} sx={{ width: 110 }} />

        <Button variant="contained" onClick={handleAdd} disabled={adding || pieceId === "" || materialId === ""} sx={{ alignSelf: "center", mt: 0.5 }}>
          {adding ? "Agregando..." : "Agregar"}
        </Button>
      </Box>

      {selectedPiece && selectedPiece.length_cut_mm == null && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          Esta pieza no tiene DXF cargado. Los costos serán 0.
        </Alert>
      )}
    </Box>
  );
}

export default AddQuotationItemForm;

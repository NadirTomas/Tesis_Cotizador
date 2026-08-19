import { useEffect, useState } from "react";

export interface UsePaginatedListResult<T> {
  paginatedItems: T[];
  page: number;
  rowsPerPage: number;
  totalCount: number;
  handlePageChange: (event: unknown, newPage: number) => void;
  handleRowsPerPageChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

/**
 * Hook para manejar paginación client-side de un arreglo de items.
 * Reset a página 0 cuando cambia el contenido (ej: después de filtrar).
 */
export function usePaginatedList<T>(items: T[], defaultRowsPerPage = 20): UsePaginatedListResult<T> {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(defaultRowsPerPage);

  // Reset a página 0 cuando cambia el número de items (después de filtrar)
  useEffect(() => {
    setPage(0);
  }, [items.length]);

  const paginatedItems = items.slice(page * rowsPerPage, (page + 1) * rowsPerPage);

  return {
    paginatedItems,
    page,
    rowsPerPage,
    totalCount: items.length,
    handlePageChange: (_: unknown, newPage: number) => setPage(newPage),
    handleRowsPerPageChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      setRowsPerPage(parseInt(e.target.value, 10));
      setPage(0);
    },
  };
}

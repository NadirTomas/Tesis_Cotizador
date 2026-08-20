import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { usePaginatedList } from "./usePaginatedList";

const items = Array.from({ length: 25 }, (_, i) => i + 1);

describe("usePaginatedList", () => {
  it("returns the first page by default", () => {
    const { result } = renderHook(() => usePaginatedList(items, 10));
    expect(result.current.paginatedItems).toEqual(items.slice(0, 10));
    expect(result.current.totalCount).toBe(25);
    expect(result.current.page).toBe(0);
  });

  it("changes page via handlePageChange", () => {
    const { result } = renderHook(() => usePaginatedList(items, 10));
    act(() => result.current.handlePageChange(null, 2));
    expect(result.current.page).toBe(2);
    expect(result.current.paginatedItems).toEqual(items.slice(20, 30));
  });

  it("changing rows per page resets to page 0", () => {
    const { result } = renderHook(() => usePaginatedList(items, 10));
    act(() => result.current.handlePageChange(null, 1));
    act(() =>
      result.current.handleRowsPerPageChange({
        target: { value: "5" },
      } as React.ChangeEvent<HTMLInputElement>)
    );
    expect(result.current.page).toBe(0);
    expect(result.current.rowsPerPage).toBe(5);
    expect(result.current.paginatedItems).toEqual(items.slice(0, 5));
  });

  it("resets to page 0 when the underlying item count changes", () => {
    const { result, rerender } = renderHook(({ list }) => usePaginatedList(list, 10), {
      initialProps: { list: items },
    });
    act(() => result.current.handlePageChange(null, 2));
    expect(result.current.page).toBe(2);

    rerender({ list: items.slice(0, 3) });
    expect(result.current.page).toBe(0);
  });
});

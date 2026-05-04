import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd

class PriceCompareApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Material Price Comparison Software")
        self.root.geometry("1100x600")

        self.df = pd.DataFrame()

        tk.Button(root, text="Load Excel File", command=self.load_file).pack(pady=10)

        search_frame = tk.Frame(root)
        search_frame.pack(pady=5)

        tk.Label(search_frame, text="Search Item / Material:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        tk.Entry(search_frame, textvariable=self.search_var, width=40).pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="Search", command=self.search_item).pack(side=tk.LEFT)

        self.tree = ttk.Treeview(root)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Button(root, text="Compare Selected Items", command=self.compare_selected).pack(pady=10)

    def load_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("CSV Files", "*.csv")]
        )

        if not file_path:
            return

        try:
            if file_path.endswith(".csv"):
                self.df = pd.read_csv(file_path)
            else:
                self.df = pd.read_excel(file_path)

            self.df.columns = self.df.columns.astype(str).str.strip()
            self.show_data(self.df)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_data(self, data):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = list(data.columns)
        self.tree["show"] = "headings"

        for col in data.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140)

        for _, row in data.iterrows():
            self.tree.insert("", tk.END, values=list(row))

    def search_item(self):
        if self.df.empty:
            messagebox.showwarning("Warning", "Please load a file first.")
            return

        keyword = self.search_var.get().lower()

        filtered = self.df[
            self.df.apply(
                lambda row: row.astype(str).str.lower().str.contains(keyword).any(),
                axis=1
            )
        ]

        self.show_data(filtered)

    def compare_selected(self):
        selected = self.tree.selection()

        if len(selected) < 2:
            messagebox.showwarning("Warning", "Select at least 2 rows to compare.")
            return

        rows = []
        for item in selected:
            rows.append(self.tree.item(item)["values"])

        compare_window = tk.Toplevel(self.root)
        compare_window.title("Price Comparison")
        compare_window.geometry("900x400")

        columns = self.tree["columns"]

        compare_tree = ttk.Treeview(compare_window)
        compare_tree.pack(fill=tk.BOTH, expand=True)

        compare_tree["columns"] = columns
        compare_tree["show"] = "headings"

        for col in columns:
            compare_tree.heading(col, text=col)
            compare_tree.column(col, width=140)

        for row in rows:
            compare_tree.insert("", tk.END, values=row)


if __name__ == "__main__":
    root = tk.Tk()
    app = PriceCompareApp(root)
    root.mainloop()
using SafeChild;

internal static class Program
{
    [STAThread]
    private static int Main()
    {
        try
        {
            using var form = new Form();
            using var grid = new DataGridView { AllowUserToAddRows = false, AutoGenerateColumns = true };
            form.Controls.Add(grid);
            _ = form.Handle;
            _ = grid.Handle;
            var ports = new List<PortEntry> { new() { Port = 80 }, new() { Port = 443 } };
            grid.DataSource = ports.ToList();
            if (grid.Rows.Count != 2) throw new Exception("Initial binding failed");
            grid.CurrentCell = grid.Rows[1].Cells[nameof(PortEntry.Port)];
            ports.RemoveAt(1);
            grid.Refresh();
            if ((int)grid.CurrentCell.Value != 443) throw new Exception("Snapshot changed before rebind");
            grid.DataSource = null; grid.DataSource = ports.ToList();
            if (grid.Rows.Count != 1) throw new Exception("Last selected row deletion failed");
            ports.RemoveAt(0);
            grid.Refresh();
            grid.DataSource = null; grid.DataSource = ports.ToList();
            if (grid.Rows.Count != 0 || grid.CurrentRow is not null) throw new Exception("Final row deletion failed");
            grid.Refresh();
            Console.WriteLine("PASS: selected last row deletion, repaint before rebind, final row deletion, empty grid refresh");
            return 0;
        }
        catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
    }
}

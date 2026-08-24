using System.IO.Compression;
using System.Text;
using System.Xml;

namespace TBC1000B.WinForms.Services;

public static class SimpleXlsxWriter
{
    public static void Write(string path, IReadOnlyList<string> headers, IReadOnlyList<object?[]> rows)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!); var temp = path + ".tmp.xlsx"; if (File.Exists(temp)) File.Delete(temp);
        try
        {
            using (var archive = ZipFile.Open(temp, ZipArchiveMode.Create))
            {
                Text(archive, "[Content_Types].xml", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/><Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/></Types>");
                Text(archive, "_rels/.rels", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>");
                Text(archive, "xl/workbook.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"모듈 상태\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>");
                Text(archive, "xl/_rels/workbook.xml.rels", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/><Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>");
                Text(archive, "xl/styles.xml", Styles()); Worksheet(archive, headers, rows);
            }
            File.Move(temp, path, true);
        }
        catch { if (File.Exists(temp)) File.Delete(temp); throw; }
    }
    private static void Worksheet(ZipArchive archive, IReadOnlyList<string> headers, IReadOnlyList<object?[]> rows)
    {
        var entry = archive.CreateEntry("xl/worksheets/sheet1.xml", CompressionLevel.Optimal); using var stream = entry.Open();
        using var x = XmlWriter.Create(stream, new XmlWriterSettings { Encoding = new UTF8Encoding(false), Indent = false, CloseOutput = false });
        x.WriteStartDocument(true); x.WriteStartElement("worksheet", "http://schemas.openxmlformats.org/spreadsheetml/2006/main");
        x.WriteStartElement("sheetViews"); x.WriteStartElement("sheetView"); x.WriteAttributeString("workbookViewId", "0"); x.WriteStartElement("pane"); x.WriteAttributeString("ySplit", "1"); x.WriteAttributeString("topLeftCell", "A2"); x.WriteAttributeString("state", "frozen"); x.WriteEndElement(); x.WriteEndElement(); x.WriteEndElement();
        x.WriteStartElement("cols"); for (var c = 1; c <= headers.Count; c++) { x.WriteStartElement("col"); x.WriteAttributeString("min", c.ToString()); x.WriteAttributeString("max", c.ToString()); x.WriteAttributeString("width", c == 1 ? "20" : "15"); x.WriteAttributeString("customWidth", "1"); x.WriteEndElement(); } x.WriteEndElement();
        x.WriteStartElement("sheetData"); Row(x, 1, headers.Cast<object?>().ToArray(), true); for (var i = 0; i < rows.Count; i++) Row(x, i + 2, rows[i], false); x.WriteEndElement();
        x.WriteStartElement("autoFilter"); x.WriteAttributeString("ref", $"A1:{Column(headers.Count)}1"); x.WriteEndElement(); x.WriteEndElement(); x.WriteEndDocument();
    }
    private static void Row(XmlWriter x, int number, IReadOnlyList<object?> values, bool header)
    {
        x.WriteStartElement("row"); x.WriteAttributeString("r", number.ToString());
        for (var i = 0; i < values.Count; i++)
        {
            var value = values[i]; x.WriteStartElement("c"); x.WriteAttributeString("r", $"{Column(i + 1)}{number}"); if (header) x.WriteAttributeString("s", "1");
            if (value is null) { x.WriteEndElement(); continue; }
            if (value is byte or short or int or long or float or double or decimal) { x.WriteElementString("v", Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture)); }
            else { x.WriteAttributeString("t", "inlineStr"); x.WriteStartElement("is"); x.WriteStartElement("t"); x.WriteAttributeString("xml", "space", null, "preserve"); x.WriteString(Convert.ToString(value) ?? ""); x.WriteEndElement(); x.WriteEndElement(); }
            x.WriteEndElement();
        }
        x.WriteEndElement();
    }
    private static string Column(int index) { var result = ""; while (index > 0) { index--; result = (char)('A' + index % 26) + result; index /= 26; } return result; }
    private static void Text(ZipArchive archive, string name, string content) { var entry = archive.CreateEntry(name, CompressionLevel.Optimal); using var writer = new StreamWriter(entry.Open(), new UTF8Encoding(false)); writer.Write(content); }
    private static string Styles() => "<?xml version=\"1.0\" encoding=\"UTF-8\"?><styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><fonts count=\"2\"><font><sz val=\"11\"/><name val=\"맑은 고딕\"/></font><font><b/><sz val=\"11\"/><name val=\"맑은 고딕\"/></font></fonts><fills count=\"3\"><fill><patternFill patternType=\"none\"/></fill><fill><patternFill patternType=\"gray125\"/></fill><fill><patternFill patternType=\"solid\"><fgColor rgb=\"FFDCEBFF\"/><bgColor indexed=\"64\"/></patternFill></fill></fills><borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs><cellXfs count=\"2\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/><xf numFmtId=\"0\" fontId=\"1\" fillId=\"2\" borderId=\"0\" xfId=\"0\" applyFont=\"1\" applyFill=\"1\" applyAlignment=\"1\"><alignment horizontal=\"center\"/></xf></cellXfs><cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles></styleSheet>";
}

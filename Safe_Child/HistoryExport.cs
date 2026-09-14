using System.IO.Compression;
using System.Text;
using System.Xml;

namespace SafeChild;

public static class HistoryExport
{
    public static void Save(string path, IReadOnlyList<string[]> rows)
    {
        var temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            if (Path.GetExtension(path).Equals(".csv", StringComparison.OrdinalIgnoreCase))
            {
                using var writer = new StreamWriter(temporary, false, new UTF8Encoding(true));
                foreach (var row in rows)
                    writer.WriteLine(string.Join(",", row.Select(CsvCell)));
            }
            else if (Path.GetExtension(path).Equals(".xlsx", StringComparison.OrdinalIgnoreCase))
                WriteExcel(temporary, rows);
            else throw new ArgumentException("파일 확장자는 .xlsx 또는 .csv를 사용하세요.");
            File.Move(temporary, path, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    private static string CsvCell(string value)
    {
        // Treat page titles and URLs as data when opened in spreadsheet software.
        var start = value.TrimStart();
        if (start.Length > 0 && "=+-@".Contains(start[0]) || value.StartsWith('\t') || value.StartsWith('\r') || value.StartsWith('\n'))
            value = "'" + value;
        return "\"" + value.Replace("\"", "\"\"") + "\"";
    }

    private static void WriteExcel(string path, IReadOnlyList<string[]> rows)
    {
        using var archive = ZipFile.Open(path, ZipArchiveMode.Create);
        WritePart(archive, "[Content_Types].xml", """
            <?xml version="1.0" encoding="utf-8"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
              <Default Extension="xml" ContentType="application/xml"/>
              <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
              <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
            </Types>
            """);
        WritePart(archive, "_rels/.rels", """
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
            </Relationships>
            """);
        WritePart(archive, "xl/workbook.xml", """
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="접속 기록" sheetId="1" r:id="rId1"/></sheets>
            </workbook>
            """);
        WritePart(archive, "xl/_rels/workbook.xml.rels", """
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
            </Relationships>
            """);
        using var stream = archive.CreateEntry("xl/worksheets/sheet1.xml").Open();
        using var xml = XmlWriter.Create(stream, new XmlWriterSettings { Encoding = new UTF8Encoding(false) });
        const string ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
        xml.WriteStartElement("worksheet", ns);
        xml.WriteStartElement("sheetData", ns);
        foreach (var row in rows)
        {
            xml.WriteStartElement("row", ns);
            foreach (var value in row)
            {
                xml.WriteStartElement("c", ns);
                xml.WriteAttributeString("t", "inlineStr");
                xml.WriteStartElement("is", ns);
                xml.WriteStartElement("t", ns);
                xml.WriteAttributeString("xml", "space", "http://www.w3.org/XML/1998/namespace", "preserve");
                xml.WriteString(ExcelText(value));
                xml.WriteEndElement(); xml.WriteEndElement(); xml.WriteEndElement();
            }
            xml.WriteEndElement();
        }
        xml.WriteEndElement(); xml.WriteEndElement();
    }

    private static string ExcelText(string value)
    {
        var result = new StringBuilder();
        for (var i = 0; i < value.Length && result.Length < 32767; i++)
        {
            var c = value[i];
            if (char.IsHighSurrogate(c) && i + 1 < value.Length && char.IsLowSurrogate(value[i + 1]))
            {
                if (result.Length > 32765) break;
                result.Append(c).Append(value[++i]);
            }
            else if (XmlConvert.IsXmlChar(c)) result.Append(c);
        }
        return result.ToString();
    }

    private static void WritePart(ZipArchive archive, string name, string content)
    {
        using var writer = new StreamWriter(archive.CreateEntry(name).Open(), new UTF8Encoding(false));
        writer.Write(content);
    }
}

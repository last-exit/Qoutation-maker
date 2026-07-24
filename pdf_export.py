"""PDF export via MS Office COM automation (win32com), with graceful offline-safe fallback."""
import os


def convert_to_pdf(input_path):
    """Converts an xlsx/docx file to PDF using the installed MS Office application via COM.

    Returns {"success": True, "pdf_path": ...} on success, or {"success": False, "error": ...}
    if Office isn't installed/available — callers should fall back to opening the source file.
    """
    input_path = os.path.abspath(input_path)
    pdf_path = os.path.splitext(input_path)[0] + ".pdf"
    suffix = os.path.splitext(input_path)[1].lower()

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        return {"success": False, "error": "pywin32 not available."}

    pythoncom.CoInitialize()
    app = None
    try:
        if suffix == ".xlsx":
            app = win32com.client.Dispatch("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            wb = app.Workbooks.Open(input_path)
            try:
                # xlTypePDF = 0
                wb.ExportAsFixedFormat(0, pdf_path)
            finally:
                wb.Close(SaveChanges=False)
        elif suffix == ".docx":
            app = win32com.client.Dispatch("Word.Application")
            app.Visible = False
            doc = app.Documents.Open(input_path)
            try:
                # wdExportFormatPDF = 17
                doc.ExportAsFixedFormat(pdf_path, 17)
            finally:
                doc.Close(SaveChanges=False)
        else:
            return {"success": False, "error": f"Unsupported file type for PDF export: {suffix}"}

        if os.path.exists(pdf_path):
            return {"success": True, "pdf_path": pdf_path}
        return {"success": False, "error": "PDF export ran but no output file was produced."}

    except Exception as e:
        return {"success": False, "error": f"PDF conversion unavailable (Office may not be installed): {e}"}
    finally:
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def open_file(path):
    """Opens a file with the OS default handler (e.g. default PDF viewer)."""
    try:
        os.startfile(path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# PowerShell script to run persona-doc-analyzer with proper volume mounting
$basePath = Get-Location

docker run --rm `
  -v "$($basePath)\PDFs:/app/PDFs" `
  -v "$($basePath)\challenge1b_input.json:/app/challenge1b_input.json" `
  -v "$($basePath)\output:/app/output" `
  --network none `
  persona-doc-analyzer
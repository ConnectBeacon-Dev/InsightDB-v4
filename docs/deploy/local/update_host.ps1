function Add-HostEntry {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Domain,

        [string]$IP = "127.0.0.1",
        [string]$HostsFile = "C:\Windows\System32\drivers\etc\hosts"
    )

    $HostEntry = "`n$IP $Domain"
    # Create the regex pattern for checking, escaping special characters
    $StrictPattern = "^127\.0\.0\.1\s+schemes\.ddpdashboard\.gov\.in"

    if ( (Get-Content -Path $HostsFile -ErrorAction Stop | Select-String -Pattern $StrictPattern) -eq $null ) {
        Add-Content -Path $HostsFile -Value $HostEntry
        Write-Host "Host entry added for $Domain." -ForegroundColor Green
    } else {
        Write-Host "Host entry for $Domain already exists. No changes made." -ForegroundColor Yellow
    }
}

# Array of domains to block
$DomainsToBlock = @(
    "login.aichatbot.schemes.ddpdashboard.gov.in",
    "chat.aichatbot.schemes.ddpdashboard.gov.in",
    "schemes.ddpdashboard.gov.in"
)

# Process all domains
foreach ($Domain in $DomainsToBlock) {
    Add-HostEntry -Domain $Domain
}
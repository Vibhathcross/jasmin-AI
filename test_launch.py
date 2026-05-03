import subprocess
import os

def jasmin_execute_launch(app_query):
    powershell_fn = r"""
    function Launch-Apps {
        param([string]$AppList)
        $Names = $AppList -split ','
        $Paths = @(
            "$env:ProgramData\Microsoft\Windows\Start Menu\Programs",
            "$env:AppData\Microsoft\Windows\Start Menu\Programs",
            "${env:ProgramFiles}",
            "${env:ProgramFiles(x86)}"
        )
        foreach ($Name in $Names) {
            $Target = $Name.Trim()
            if (-not $Target) { continue }
            Write-Host "Searching for: $Target"
            # Using Include instead of Filter for better wildcards in some cases
            $Match = Get-ChildItem -Path $Paths -Include "*$Target*" -Recurse -ErrorAction SilentlyContinue | 
                     Where-Object { $_.Extension -in '.exe', '.lnk' } | Select-Object -First 1
            if ($Match) { 
                Write-Host "Found: $($Match.FullName)"
                # Start-Process $Match.FullName
            } else {
                Write-Host "Not found in paths: $Target"
            }
        }
    }
    """
    
    full_command = f"{powershell_fn} ; Launch-Apps -AppList '{app_query}'"
    
    try:
        result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", full_command], capture_output=True, text=True)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return "Done"
    except Exception as e:
        return str(e)

print(jasmin_execute_launch("Chrome, VS Code, Terminal"))

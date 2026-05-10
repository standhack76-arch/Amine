name: github rdp tailscale edition
on:
  workflow_dispatch:
    inputs:
      password:
        description: 'set rdp password'
        required: true
        default: 'Atay@Bna3na3#2026'

jobs:
  build:
    runs-on: windows-latest
    steps:
      - name: initializing environment
        run: echo "starting server deployment..."

      - name: installing tailscale
        run: |
          echo "downloading tailscale..."
          invoke-webrequest -uri 'https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe' -outfile 'tailscale.exe'
          start-process -filepath "tailscale.exe" -argumentlist "/quiet" -wait
          echo "waiting for service..."
          start-sleep -seconds 15
          echo "tailscale setup complete."

      - name: authenticating tailscale
        run: |
          echo "linking to tailscale network..."
          & "c:\program files\tailscale\tailscale.exe" up --authkey=${{ secrets.TS_KEY }} --hostname=cloud-rdp-server --accept-routes
          echo "authentication successful."

      - name: disabling password policy
        run: |
          echo "killing windows password complexity requirements..."
          secedit /export /cfg config.inf
          (get-content config.inf) -replace 'PasswordComplexity = 1', 'PasswordComplexity = 0' | set-content config.inf
          secedit /configure /db $env:temp\temp.sdb /cfg config.inf /areas SECURITYPOLICY
          echo "policy disabled."

      - name: configuring remote desktop
        run: |
          echo "setting up user credentials..."
          net user runneradmin "${{ github.event.inputs.password }}" /y
          
          echo "configuring registry and firewall..."
          Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -name "fDenyTSConnections" -value 0
          Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue
          Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -name "UserAuthentication" -value 1
          
          echo "rdp protocol enabled."
          exit 0

      - name: maintaining connection
        run: |
          echo "=========================================="
          echo "server is live"
          echo "username: runneradmin"
          echo "password: ${{ github.event.inputs.password }}"
          echo "internal ip address:"
          & "c:\program files\tailscale\tailscale.exe" ip -4
          echo "=========================================="
          while ($true) {
            echo "keep-alive: $(get-date)"
            start-sleep -seconds 300
          }

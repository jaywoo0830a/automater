# Mobile Proxy Setup

Android + Tailscale + Termux를 사용하여 서버 트래픽을 한국 모바일 IP로 프록시하는 방법.

## 구조

```
서버 (싱가포르)
  └─ SSH 터널 (localhost:1080)
       └─ Tailscale (100.119.27.119)
            └─ 안드로이드 Termux (sshd:8022)
                 └─ 한국 모바일 데이터 (5G/LTE)
```

## 1. 안드로이드 설정 (최초 1회)

### Tailscale 설치
- Play Store에서 **Tailscale** 설치
- 로그인 (서버와 동일한 계정)
- Tailscale IP 확인 (예: `100.119.27.119`)

### Termux 설치 + SSH 서버
```bash
pkg install openssh -y
passwd          # 비밀번호 설정
sshd            # SSH 서버 시작 (포트 8022)
```

## 2. 서버 설정 (최초 1회)

### Tailscale 설치
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

## 3. 프록시 연결 (매번)

### 안드로이드에서
```bash
# Termux 앱 열기
sshd
```

### 서버에서
```bash
# SSH SOCKS5 터널 열기
ssh -D 1080 -N -f -p 8022 u0_a314@100.119.27.119

# 확인
curl --socks5 localhost:1080 ifconfig.me
# → 한국 모바일 IP가 출력되면 성공
```

## 4. 캠페인 DSL 설정

```yaml
accounts:
  - username: myaccount
    password: mypass
    proxy: socks5://localhost:1080
```

## 5. 연결 해제

```bash
# 서버에서 터널 종료
pkill -f "ssh -D 1080"
```

## 주의사항

- 안드로이드 화면이 꺼져도 Termux는 유지됨 (알림 바에 표시)
- Termux가 종료되면 `sshd`를 다시 실행해야 함
- `exit node`는 사용하지 말 것 — SSH 접속이 끊김
- 모바일 데이터가 꺼지면 프록시도 끊김

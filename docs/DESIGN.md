# UI/UX System & Design Guidelines - LETATEC

## 1. Aesthetic Identity
LETATEC utilizes a dark, futuristic corporate theme featuring high-contrast text, glassmorphism overlays, and subtle animated borders. 

*   **Backgrounds**: `#07070A` (Core background), `#0F1722` (Card surface).
*   **Accents**: Cyan (`#67E8F9`), Emerald green (`#10B981` / `#34D399`), Amber/Gold (`#F59E0B`).
*   **Borders**: `white/[0.05]` or `white/[0.08]` to define panels cleanly.

## 2. Typography
*   **Headers**: Outfit or Inter (letter-spacing: tight, tracking-tight).
*   **Body**: Inter or Roboto (font-size: 13px/14px for maximum information density).
*   **Metrics / Codes**: Space Grotesk or SF Mono (font-size: 11px/12px).

## 3. Glassmorphism Principles
*   Apply `backdrop-blur-sm` and `bg-white/[0.02]` or `bg-[#0F1722]/80`.
*   Maintain a 1px border with `border-white/[0.05]` to give the illusion of physical plates.

## 4. UI Components & States
*   **Hover states**: All buttons must transition with `transition-all duration-300` and display slight scale boosts or border glow.
*   **Empty states**: Use icons of style `lucide` at opacity 30% with clear action labels (e.g., "Queue is empty. Drop files to configure ingestion.").
*   **Loading states**: Pulsing glow or spinner rotations centered in panels.

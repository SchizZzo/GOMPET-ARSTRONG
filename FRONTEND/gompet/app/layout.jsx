export const metadata = {
  title: "Gompet WebSocket Test",
  description: "Testowe połączenie WebSocket do powiadomień."
};

export default function RootLayout({ children }) {
  return (
    <html lang="pl">
      <body>{children}</body>
    </html>
  );
}

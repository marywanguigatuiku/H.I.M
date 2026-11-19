import "./globals.css";

export const metadata = { title: "Admin · Read-Aloud", description: "Manage people, access and content" };
export const viewport = { width: "device-width", initialScale: 1, themeColor: "#0E1018" };

// Uses the same saved theme as the library (they share the same address).
const themeScript = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}

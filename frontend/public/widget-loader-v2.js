(function() {
  // Configuration
  // --------------------------------------------------------
  // IMPORTANT: When you deploy this project to the internet (e.g., AWS/Vercel),
  // you MUST change this URL to your live domain (e.g., https://my-ai-widget.com).
  // The client's website will load this URL inside the iframe.
  // --------------------------------------------------------
  var WIDGET_URL = "http://localhost:5173?mode=widget"; 
  var IFRAME_ID = "amoeba-ai-widget-iframe";

  // Check if widget already exists
  if (document.getElementById(IFRAME_ID)) return;

  // Create Iframe
  var iframe = document.createElement("iframe");
  iframe.id = IFRAME_ID;
  iframe.src = WIDGET_URL;
  
  // Style Iframe (Floating Bottom Right)
  iframe.style.position = "fixed";
  iframe.style.bottom = "20px";
  iframe.style.right = "20px";
  iframe.style.width = "85px"; // Clean size for bubble
  iframe.style.height = "85px";
  iframe.style.border = "none";
  iframe.style.outline = "none";
  iframe.style.background = "transparent";
  iframe.style.borderRadius = "0px";
  iframe.style.boxShadow = "none";
  iframe.style.zIndex = "2147483647"; // Max Z-Index
  iframe.style.transition = "width 0.25s cubic-bezier(0.4, 0, 0.2, 1), height 0.25s cubic-bezier(0.4, 0, 0.2, 1)";
  iframe.style.overflow = "visible";
  iframe.setAttribute("scrolling", "no");
  iframe.setAttribute("allowtransparency", "true");
  
  // Optional: Responsive on mobile
  if (window.innerWidth < 480) {
    iframe.style.width = "85px";
    iframe.style.height = "85px";
  }

  document.body.appendChild(iframe);

  // Listen for messages from the widget
  window.addEventListener("message", function(event) {
    // if (event.origin !== WIDGET_URL) return; // Security Check (Enable in Prod)
    
    // 1. Core Widget Control
    if (event.data === "close-widget") {
      iframe.style.display = "none";
    }
    
    // 2. Advanced: Handle Actions from AI (Navigation, etc.)
    // The React App will postMessage: { type: 'AMOEBA_ACTION', action: 'NAVIGATE', payload: '/...' }
    if (event.data && event.data.type === 'AMOEBA_ACTION') {
        console.log("🚀 Amoeba Action Received:", event.data);
        
        if (event.data.action === 'NAVIGATE') {
            console.log("Testing Navigation to:", event.data.payload);
            // In a real app, you might use: window.location.href = event.data.payload;
            // Or if Single Page App: router.push(event.data.payload);
            // alert("AI requested navigation to: " + event.data.payload);
            window.location.href = event.data.payload;
        }
    }
    // 3. Dynamic Resizing (Zero ghost box, 100% transparent iframe container)
    if (event.data && event.data.type === 'AMOEBA_RESIZE') {
        if (event.data.state === 'EXPANDED') {
            if (window.innerWidth < 480) {
                iframe.style.width = "100vw";
                iframe.style.height = "100vh";
                iframe.style.bottom = "0px";
                iframe.style.right = "0px";
            } else {
                iframe.style.width = "410px";
                iframe.style.height = "640px";
                iframe.style.bottom = "20px";
                iframe.style.right = "20px";
            }
            iframe.style.boxShadow = "none"; // Absolutely NO outer shadow on iframe
            iframe.style.borderRadius = "0px";
            iframe.style.background = "transparent";
            iframe.style.border = "none";
            iframe.style.outline = "none";
        } else {
            iframe.style.width = "85px"; // Clean size for floating bubble
            iframe.style.height = "85px";
            iframe.style.bottom = "20px";
            iframe.style.right = "20px";
            iframe.style.boxShadow = "none";
            iframe.style.borderRadius = "0px";
            iframe.style.background = "transparent";
            iframe.style.border = "none";
            iframe.style.outline = "none";
        }
    }
  });

  // 4. Auto-Discovery: Scan User's Page for Navigation Links
  // This fulfills the "analyze the codebase" requirement by analyzing the RENDERED result (The Menu).
  function scanAndLearn() {
      console.log("🕵️ Amoeba (v2): Scanning page for navigation links...");
      const links = document.querySelectorAll("a");
      const discovered = [];
      const seen = new Set();
      
      links.forEach(link => {
          const text = link.innerText.trim();
          const href = link.getAttribute('href'); // Get raw attribute to capture relative paths
          
          if (!text || !href) return;
          if (text.length < 2) return; // Skip icons/single chars
          if (href.startsWith("#") || href.startsWith("javascript")) return;
          if (seen.has(text + href)) return;
          
          seen.add(text + href);
          discovered.push({ label: text, path: href });
      });

      if (discovered.length > 0) {
          console.log(`🕵️ Amoeba: Found ${discovered.length} links. Sending to Brain.`);
          
          // Wait for iframe to accept messages
          setTimeout(() => {
              iframe.contentWindow.postMessage({
                  type: "AMOEBA_DISCOVERED_ROUTES",
                  routes: discovered
              }, "*");
          }, 2000);
      }
  }

  // Run scan after slight delay to ensure dynamic menus load
  window.addEventListener("load", () => setTimeout(scanAndLearn, 1500));
  // Also run immediately in case we loaded async
  setTimeout(scanAndLearn, 2000);

})(); // <--- Properly closed IIFE

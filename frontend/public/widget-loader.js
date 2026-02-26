(function() {
  // Configuration
  // --------------------------------------------------------
  // IMPORTANT: When you deploy this project to the internet (e.g., AWS/Vercel),
  // you MUST change this URL to your live domain (e.g., https://my-ai-widget.com).
  // The client's website will load this URL inside the iframe.
  // --------------------------------------------------------
  // Detect API Key from Script Tag
  var currentScript = document.currentScript || (function() {
      var scripts = document.getElementsByTagName('script');
      return scripts[scripts.length - 1];
  })();
  var apiKey = currentScript.getAttribute('data-api-key');

  var WIDGET_URL = "http://localhost:5173?mode=widget"; 
  if (apiKey) {
      WIDGET_URL += "&api_key=" + encodeURIComponent(apiKey);
  } 
  var IFRAME_ID = "amoeba-ai-widget-iframe";

  // Check if widget already exists
  if (document.getElementById(IFRAME_ID)) return;

  // Create Iframe
  var iframe = document.createElement("iframe");
  iframe.id = IFRAME_ID;
  iframe.src = WIDGET_URL;
  
  // Style Iframe (Floating Buttom Right)
  iframe.style.position = "fixed";
  iframe.style.bottom = "20px";
  iframe.style.right = "20px";
  iframe.style.width = "120px"; // Safe size for bubble
  iframe.style.height = "120px";
  iframe.style.border = "none";
  iframe.style.borderRadius = "12px";
  iframe.style.boxShadow = "none";
  iframe.style.zIndex = "2147483647"; // Max Z-Index
  iframe.style.transition = "all 0.3s ease";
  
  // Optional: Responsive on mobile
  if (window.innerWidth < 480) {
    iframe.style.width = "90%";
    iframe.style.right = "5%";
    iframe.style.height = "80%";
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
    // 3. Dynamic Resizing (Fixes "Invisible Box" & "Crease" issues)
    if (event.data && event.data.type === 'AMOEBA_RESIZE') {
        if (event.data.state === 'EXPANDED') {
            iframe.style.width = "400px";
            iframe.style.height = "600px";
            iframe.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)"; // Shadow only when open
            iframe.style.borderRadius = "12px";
        } else {
            iframe.style.width = "120px"; // Just enough for bubble
            iframe.style.height = "120px";
            iframe.style.boxShadow = "none"; // No shadow when closed (removes crease)
            iframe.style.borderRadius = "0px";
        }
    }
  });

  // 4. Auto-Discovery: Scan User's Page for Navigation Links
  // This fulfills the "analyze the codebase" requirement by analyzing the RENDERED result (The Menu).
  function scanAndLearn() {
      console.log("🕵️ Amoeba: Scanning page for navigation links...");
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

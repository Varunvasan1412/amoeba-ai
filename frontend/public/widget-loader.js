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

  // 4. Auto-Discovery Engine v9.0 (Atomic Scan)
  function scanAndLearn() {
      const discoveredRoutes = [];
      const seenRoutes = new Set();
      const discoveredFields = [];
      const seenElements = new Set();
      const rawInputDetails = [];

      function deepScan(root) {
          if (!root || seenElements.has(root)) return;
          seenElements.add(root);

          try {
              // 1. Scan Links
              root.querySelectorAll("a").forEach(link => {
                  const text = link.innerText.trim();
                  const href = link.getAttribute('href');
                  if (!text || !href || text.length < 2 || href.startsWith("#")) return;
                  if (seenRoutes.has(text + href)) return;
                  seenRoutes.add(text + href);
                  discoveredRoutes.push({ label: text, path: href });
              });

              // 2. Scan Form Elements
              const selector = "input, select, textarea, [role='textbox'], [role='combobox']";
              const candidates = root.querySelectorAll(selector);
              
              candidates.forEach(el => {
                  if (el.type === "hidden" || el.tagName === "A") return;
                  
                  const name = el.name || el.id || el.getAttribute("data-field");
                  rawInputDetails.push({ id: el.id, name: el.name, type: el.tagName, class: el.className });

                  if (!name || name.includes("DataTables") || name.startsWith("_")) return;

                  let labelText = "";
                  // Aggressive Label Search
                  const linked = document.querySelector(`label[for="${el.id}"]`) || el.closest("label");
                  if (linked) labelText = linked.innerText;

                  if (!labelText || labelText.trim().length < 2) {
                      let prev = el.previousElementSibling;
                      if (prev && prev.innerText && prev.innerText.trim().length > 1) labelText = prev.innerText;
                  }

                  if (!labelText || labelText.trim().length < 2) {
                      let p = el.parentElement;
                      if (p && p.innerText && p.innerText.trim().length > 1) labelText = p.innerText.split("\n")[0];
                  }

                  if (!labelText || labelText.trim().length < 2) {
                      labelText = el.placeholder || el.title || el.getAttribute("aria-label");
                  }

                  if (labelText) {
                      const cleanLabel = labelText.replace(/[:*]/g, "").trim();
                      if (cleanLabel.length >= 2) {
                          discoveredFields.push({
                              label: cleanLabel,
                              name: name,
                              type: el.type || el.tagName.toLowerCase(),
                              required: el.required || false
                          });
                      }
                  }
              });

              // 3. Shadow DOM
              root.querySelectorAll("*").forEach(el => {
                  if (el.shadowRoot) deepScan(el.shadowRoot);
              });

              // 4. Iframe / Frameset Scan
              root.querySelectorAll("iframe, frame").forEach(frame => {
                  if (frame.id === IFRAME_ID) return;
                  try {
                      if (frame.contentDocument) deepScan(frame.contentDocument);
                  } catch (e) {}
              });

          } catch (e) {}
      }

      // Try absolute top window if possible, otherwise current
      deepScan(document);
      
      // DIAGNOSTIC LOG
      console.log(`🔬 Amoeba diagnostics: Seen inputs:`, rawInputDetails);
      console.log(`🔬 Amoeba Result: Mapped ${discoveredFields.length} fields.`);

      if (discoveredFields.length > 0 || discoveredRoutes.length > 0) {
          const payload = {
              type: "AMOEBA_DISCOVERED_FIELDS",
              fields: discoveredFields,
              path: window.location.pathname
          };
          iframe.contentWindow.postMessage(payload, "*");
          if (discoveredRoutes.length > 0) {
              iframe.contentWindow.postMessage({ type: "AMOEBA_DISCOVERED_ROUTES", routes: discoveredRoutes }, "*");
          }
      }
  }

  setInterval(scanAndLearn, 10000); 
  window.addEventListener("load", () => setTimeout(scanAndLearn, 1000));
  setTimeout(scanAndLearn, 2000);


  setInterval(scanAndLearn, 8000); 
  window.addEventListener("load", () => setTimeout(scanAndLearn, 1000));
  setTimeout(scanAndLearn, 2000);


  setInterval(scanAndLearn, 8000); 
  window.addEventListener("load", () => setTimeout(scanAndLearn, 1000));
  setTimeout(scanAndLearn, 2000);


  setInterval(scanAndLearn, 8000); 
  window.addEventListener("load", () => setTimeout(scanAndLearn, 1000));
  setTimeout(scanAndLearn, 2000);




  // Run scan after slight delay to ensure dynamic menus load
  window.addEventListener("load", () => setTimeout(scanAndLearn, 1500));
  // Also run immediately in case we loaded async
  setTimeout(scanAndLearn, 2000);

})(); // <--- Properly closed IIFE

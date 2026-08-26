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

  // Dynamically detect where this script was loaded from (localhost vs live IP)
  var scriptOrigin = currentScript.src ? new URL(currentScript.src).origin : "http://localhost:5173";
  var WIDGET_URL = scriptOrigin + "?mode=widget"; 
  
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
  iframe.allow = "microphone";
  
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
  iframe.style.overflow = "hidden";
  iframe.setAttribute("scrolling", "no");
  
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
            iframe.style.width = "420px";
            iframe.style.height = "650px";
            iframe.style.boxShadow = "0 4px 20px rgba(0,0,0,0.2)"; // Shadow only when open
            iframe.style.borderRadius = "16px";
        } else {
            iframe.style.width = "120px"; // Just enough for bubble
            iframe.style.height = "120px";
            iframe.style.boxShadow = "none"; // No shadow when closed (removes crease)
            iframe.style.borderRadius = "0px";
        }
    }
  });

  // 4. Auto-Discovery Engine v10.0 (Resilient Scan)
  function scanAndLearn() {
      const discoveredRoutes = [];
      const seenRoutes = new Set();
      const discoveredFields = [];
      const seenElements = new Set();

      function deepScan(root) {
          if (!root || seenElements.has(root)) return;
          seenElements.add(root);

          try {
              // 1. Scan Links for Navigation Intelligence
              root.querySelectorAll("a").forEach(link => {
                  const text = link.innerText.trim();
                  const href = link.getAttribute('href');
                  if (!text || !href || text.length < 2 || href.startsWith("#")) return;
                  if (seenRoutes.has(text + href)) return;
                  seenRoutes.add(text + href);
                  discoveredRoutes.push({ label: text, path: href });
              });

              // 2. Scan Form Elements with Agnostic Discovery
              const selector = "input, select, textarea, [role='textbox'], [role='combobox']";
              const candidates = root.querySelectorAll(selector);
              
              candidates.forEach(el => {
                  if (el.type === "hidden" || el.tagName === "A") return;
                  
                  const name = el.name || el.id || el.getAttribute("data-field");
                  if (!name || name.includes("DataTables") || name.startsWith("_") || name === "search") return;

                  let labelText = "";

                  // --- MULTI-TIER LABEL DISCOVERY ---
                  
                  // Priority 1: Browser Native labels collection
                  if (el.labels && el.labels.length > 0) {
                      labelText = el.labels[0].innerText;
                  }

                  // Priority 2: Explicit label[for] or closest label
                  if (!labelText) {
                      const linked = document.querySelector(`label[for="${el.id}"]`) || el.closest("label");
                      if (linked) labelText = linked.innerText;
                  }

                  // Priority 3: Previous Sibling (Common in table-based layouts)
                  if (!labelText || labelText.trim().length < 2) {
                      let prev = el.previousElementSibling;
                      if (prev && prev.innerText && prev.innerText.trim().length > 1) labelText = prev.innerText;
                  }

                  // Priority 4: Parent -> Parent structure (Common in Div-based ERPs)
                  if (!labelText || labelText.trim().length < 2) {
                      let p = el.parentElement;
                      if (p && p.innerText && p.innerText.trim().length > 1) {
                          // Take the first line to avoid wrapping issues
                          labelText = p.innerText.split("\n")[0].trim();
                      }
                  }

                  // Priority 5: Attributes (Placeholder, ARIA, Title)
                  if (!labelText || labelText.trim().length < 2) {
                      labelText = el.placeholder || el.title || el.getAttribute("aria-label");
                  }

                  // Priority 6: Fallback to Name (UX Improvement: customer_name -> Customer Name)
                  if (!labelText || labelText.trim().length < 2) {
                      labelText = name.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, '$1 $2').toUpperCase();
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

              // 3. Recursive Shadow DOM Scan
              root.querySelectorAll("*").forEach(el => {
                  if (el.shadowRoot) deepScan(el.shadowRoot);
              });

              // 4. Multi-Frame Discovery (Iframe / Frameset)
              root.querySelectorAll("iframe, frame").forEach(frame => {
                  if (frame.id === IFRAME_ID) return;
                  try {
                      if (frame.contentDocument) deepScan(frame.contentDocument);
                  } catch (e) {
                      // Silently skip cross-origin iframes
                  }
              });

          } catch (e) {
              console.warn("⚠️ [Amoeba] Scan partial failure:", e);
          }
      }

      // Start recursive scan from main document
      deepScan(document);
      
      console.log(`🔬 [Amoeba UI] Result: Discovered ${discoveredFields.length} fields on page: ${window.location.pathname}`);

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

  // --- CONTROL TIMERS ---
  // We run a scan on load, after a delay, and periodically (every 10s)
  window.addEventListener("load", function() {
      setTimeout(scanAndLearn, 1500); // Initial 1.5s delay
  });

  // Fallback in case load event already fired
  if (document.readyState === "complete") {
      setTimeout(scanAndLearn, 1500);
  } else {
      setTimeout(scanAndLearn, 3000); // Late fallback to ensure dynamic forms render
  }

  setInterval(scanAndLearn, 10000); // Periodic reinforcement

})(); 

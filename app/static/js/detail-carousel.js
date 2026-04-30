(() => {
  const carousel = document.querySelector("[data-carousel]");
  if (carousel) {
    const frame = carousel;
    const image = carousel.querySelector("[data-carousel-image]");
    const overlay = carousel.querySelector("[data-carousel-overlay]");
    const prevButton = carousel.querySelector("[data-carousel-prev]");
    const nextButton = carousel.querySelector("[data-carousel-next]");
    const counter = carousel.querySelector("[data-carousel-counter]");
    const imagesScript = carousel.querySelector("[data-carousel-images]");
    const enquiryCard = document.querySelector(".enquiry-card");

    if (frame) {
      frame.style.position = "relative";
      frame.style.width = "100%";
      frame.style.aspectRatio = "1 / 1";
      frame.style.maxHeight = "none";
      frame.style.height = "auto";
      frame.style.minHeight = "0";
      frame.style.overflow = "hidden";
      frame.style.background = "var(--bg)";
    }

    if (overlay) {
      overlay.style.position = "absolute";
      overlay.style.inset = "0";
      overlay.style.zIndex = "20";
      overlay.style.display = "flex";
      overlay.style.alignItems = "center";
      overlay.style.justifyContent = "space-between";
      overlay.style.pointerEvents = "none";
    }

    if (image) {
      image.style.width = "100%";
      image.style.height = "100%";
      image.style.objectFit = "contain";
      image.style.display = "block";
      image.style.background = "var(--bg)";
    }

    if (prevButton) {
      prevButton.style.pointerEvents = "auto";
      prevButton.style.marginLeft = "16px";
      prevButton.style.position = "relative";
      prevButton.style.zIndex = "21";
      prevButton.style.width = "40px";
      prevButton.style.height = "40px";
      prevButton.style.borderRadius = "999px";
      prevButton.style.background = "rgba(255, 255, 255, 0.72)";
      prevButton.style.color = "#111827";
      prevButton.style.border = "1px solid rgba(17, 24, 39, 0.08)";
      prevButton.style.boxShadow = "0 8px 16px rgba(15, 23, 42, 0.14)";
      prevButton.style.display = "inline-flex";
      prevButton.style.alignItems = "center";
      prevButton.style.justifyContent = "center";
      prevButton.style.fontSize = "16px";
      prevButton.style.fontWeight = "900";
      prevButton.style.lineHeight = "1";
      prevButton.style.textDecoration = "none";
      prevButton.style.cursor = "pointer";
      prevButton.style.transition = "background 0.15s ease, box-shadow 0.15s ease";
    }

    if (nextButton) {
      nextButton.style.pointerEvents = "auto";
      nextButton.style.marginRight = "16px";
      nextButton.style.position = "relative";
      nextButton.style.zIndex = "21";
      nextButton.style.width = "40px";
      nextButton.style.height = "40px";
      nextButton.style.borderRadius = "999px";
      nextButton.style.background = "rgba(255, 255, 255, 0.72)";
      nextButton.style.color = "#111827";
      nextButton.style.border = "1px solid rgba(17, 24, 39, 0.08)";
      nextButton.style.boxShadow = "0 8px 16px rgba(15, 23, 42, 0.14)";
      nextButton.style.display = "inline-flex";
      nextButton.style.alignItems = "center";
      nextButton.style.justifyContent = "center";
      nextButton.style.fontSize = "16px";
      nextButton.style.fontWeight = "900";
      nextButton.style.lineHeight = "1";
      nextButton.style.textDecoration = "none";
      nextButton.style.cursor = "pointer";
      nextButton.style.transition = "background 0.15s ease, box-shadow 0.15s ease";
    }

    if (counter) {
      counter.style.position = "absolute";
      counter.style.right = "16px";
      counter.style.bottom = "16px";
      counter.style.zIndex = "21";
      counter.style.background = "rgba(17, 24, 39, 0.72)";
      counter.style.color = "#fff";
      counter.style.padding = "5px 10px";
      counter.style.borderRadius = "999px";
      counter.style.fontSize = "11px";
      counter.style.fontWeight = "700";
      counter.style.letterSpacing = "0.02em";
      counter.style.boxShadow = "0 8px 16px rgba(15, 23, 42, 0.18)";
      counter.style.backdropFilter = "blur(8px)";
    }

    const syncFrameSizing = () => {
      if (!frame) return;
      if (window.innerWidth <= 900 || !enquiryCard) {
        frame.style.aspectRatio = "1 / 1";
        frame.style.height = "auto";
        frame.style.minHeight = "0";
        frame.style.maxHeight = "none";
      } else {
        const cardHeight = Math.round(enquiryCard.getBoundingClientRect().height);
        frame.style.aspectRatio = "auto";
        frame.style.height = `${cardHeight}px`;
        frame.style.minHeight = `${cardHeight}px`;
        frame.style.maxHeight = `${cardHeight}px`;
      }
      if (image) {
        image.style.objectFit = "contain";
      }
    };

    syncFrameSizing();
    window.addEventListener("resize", syncFrameSizing);
    if (window.ResizeObserver && enquiryCard) {
      const observer = new ResizeObserver(() => syncFrameSizing());
      observer.observe(enquiryCard);
    }

    if (image && imagesScript) {
      let images = [];
      try {
        images = JSON.parse(imagesScript.textContent || "[]");
      } catch (_error) {
        images = [];
      }

      if (images.length > 0) {
        let currentIndex = 0;
        const listingTitle = image.dataset.listingTitle || "Listing";

        const updateCarousel = () => {
          image.src = images[currentIndex];
          image.alt = `${listingTitle} image ${currentIndex + 1}`;
          if (counter) {
            counter.textContent = `${currentIndex + 1} / ${images.length}`;
          }
        };

        if (prevButton) {
          prevButton.addEventListener("click", () => {
            currentIndex = (currentIndex - 1 + images.length) % images.length;
            updateCarousel();
          });
        }

        if (nextButton) {
          nextButton.addEventListener("click", () => {
            currentIndex = (currentIndex + 1) % images.length;
            updateCarousel();
          });
        }

        updateCarousel();
      }
    }
  }

  const messageInput = document.querySelector("[data-enquiry-message]");
  const messageCounter = document.querySelector("[data-char-counter]");
  if (!messageInput || !messageCounter) return;

  const maxLength = 1500;

  const updateCounter = () => {
    if (messageInput.value.length > maxLength) {
      messageInput.value = messageInput.value.slice(0, maxLength);
    }

    const length = messageInput.value.length;
    messageCounter.textContent = `${length} / ${maxLength}`;
    messageCounter.classList.remove("is-warning", "is-danger");

    if (length >= maxLength) {
      messageCounter.classList.add("is-danger");
    } else if (length >= 1300) {
      messageCounter.classList.add("is-warning");
    }
  };

  messageInput.addEventListener("input", updateCounter);
  updateCounter();
})();

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

    if (frame) {
      frame.style.position = "relative";
      frame.style.width = "100%";
      frame.style.height = "340px";
      frame.style.minHeight = "340px";
      frame.style.overflow = "hidden";
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
      image.style.objectFit = "cover";
      image.style.display = "block";
    }

    if (prevButton) {
      prevButton.style.pointerEvents = "auto";
      prevButton.style.marginLeft = "16px";
      prevButton.style.position = "relative";
      prevButton.style.zIndex = "21";
    }

    if (nextButton) {
      nextButton.style.pointerEvents = "auto";
      nextButton.style.marginRight = "16px";
      nextButton.style.position = "relative";
      nextButton.style.zIndex = "21";
    }

    if (counter) {
      counter.style.position = "absolute";
      counter.style.right = "14px";
      counter.style.bottom = "14px";
      counter.style.zIndex = "21";
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

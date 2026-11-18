// Show / hide the password. Works for any button with class "basera-toggle"
// whose aria-controls points at a password input, so teammates can reuse it
// on the Sign Up page.
document.querySelectorAll(".basera-toggle").forEach(function (button) {
  var input = document.getElementById(button.getAttribute("aria-controls"));
  if (!input) return;

  button.addEventListener("click", function () {
    var showing = input.type === "text";
    input.type = showing ? "password" : "text";
    button.textContent = showing ? "Show" : "Hide";
    button.setAttribute("aria-pressed", String(!showing));
    button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    input.focus();

    // Small "pop" so the label change is noticeable
    button.classList.remove("is-swapping");
    void button.offsetWidth; // restart the animation
    button.classList.add("is-swapping");
  });
});

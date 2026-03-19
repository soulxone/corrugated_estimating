// Rename "Corrugated Estimating" to "Estimating" on the desk page
$(document).ready(function () {
	setTimeout(function () {
		document.querySelectorAll(".icon-title").forEach(function (el) {
			if (el.textContent.trim() === "Corrugated Estimating") {
				el.textContent = "Estimating";
			}
		});
	}, 500);
});

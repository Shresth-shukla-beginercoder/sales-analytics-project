const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file");
const fileName = document.getElementById("file-name");

["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add("drag-over");
    });
});

["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, () => {
        dropZone.classList.remove("drag-over");
    });
});

dropZone.addEventListener("drop", (event) => {
    event.preventDefault();

    const droppedFile = event.dataTransfer.files[0];

    if (!droppedFile) {
        return;
    }

    const name = droppedFile.name.toLowerCase();

    if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) {
        fileInput.value = "";
        fileName.textContent = "Only CSV and Excel files are allowed";
        return;
    }

    const transfer = new DataTransfer();
    transfer.items.add(droppedFile);
    fileInput.files = transfer.files;

    showFileName();
});
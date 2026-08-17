// Syncs the colors typed in the Product Image rows into a dropdown
// (datalist) suggestion list for the Product Variant "Color" field,
// so the same color name doesn't need to be typed twice.
django.jQuery(function ($) {
  var DATALIST_ID = 'id_image_colors_datalist';

  function getDatalist() {
    var datalist = document.getElementById(DATALIST_ID);
    if (!datalist) {
      datalist = document.createElement('datalist');
      datalist.id = DATALIST_ID;
      document.body.appendChild(datalist);
    }
    return datalist;
  }

  function collectImageColors() {
    var colors = [];
    $('#images-group input[id$="-color"]').each(function () {
      var val = $(this).val().trim();
      if (val && colors.indexOf(val) === -1) colors.push(val);
    });
    return colors;
  }

  function refreshDatalist() {
    var datalist = getDatalist();
    datalist.innerHTML = '';
    collectImageColors().forEach(function (color) {
      var option = document.createElement('option');
      option.value = color;
      datalist.appendChild(option);
    });
  }

  function attachDatalistToVariantColorInputs() {
    $('#variants-group input[id$="-color"]').each(function () {
      $(this).attr('list', DATALIST_ID);
      $(this).attr('placeholder', 'Pick from image colors above');
    });
  }

  function refreshAll() {
    refreshDatalist();
    attachDatalistToVariantColorInputs();
  }

  // Re-sync whenever a color is typed/changed in an image row
  $(document).on('input change', '#images-group input[id$="-color"]', refreshDatalist);

  // Re-sync when a new image or variant row is added (Django's "Add another" button)
  $(document).on('formset:added', function () {
    refreshAll();
  });

  // Initial sync on page load
  refreshAll();
});

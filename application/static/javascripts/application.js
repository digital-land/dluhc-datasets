(function () {
  'use strict';

  (function () {

    // configuration object
    let config = {
      inputSelector: '.govuk-input#name',
      outputSelector: '.govuk-input#reference'
    };

    // slugify the value passed in and return it
    function slugify(input) {
        if (!input)
            return '';

        // make lower case and trim
        var slug = input.toLowerCase().trim();

        // remove accents from charaters
        slug = slug.normalize('NFD').replace(/[\u0300-\u036f]/g, '');

        // replace invalid chars with spaces
        slug = slug.replace(/[^a-z0-9\s-]/g, ' ').trim();

        // replace multiple spaces or hyphens with a single hyphen
        slug = slug.replace(/[\s-]+/g, '-');

        return slug;
    }

    function init () {

      const $input = document.querySelector(config.inputSelector);
      const $output = document.querySelector(config.outputSelector);

      if ($input != null && $output != null) {
        $input.onkeyup = () => {
          $output.value = slugify($input.value);
        };
      }
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  })();

})();

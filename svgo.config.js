module.exports = {
  multipass: true,
  plugins: [
    {
      name: 'preset-default',
      params: {
        overrides: {
          // Garder les animations
          removeUnknownsAndDefaults: false,
          removeUselessStrokeAndFill: false,
          // Optimiser les chemins
          convertPathData: true,
          // Garder les IDs pour les animations et aria-describedby
          cleanupIds: false,
          // Optimiser les styles
          inlineStyles: true,
          minifyStyles: true,
        },
      },
    },
    // Ne pas supprimer les éléments d'accessibilité
    {
      name: 'removeDoctype',
      active: true,
    },
    {
      name: 'removeXMLProcInst',
      active: true,
    },
    {
      name: 'removeComments',
      active: true,
    },
    {
      name: 'removeMetadata',
      active: true,
    },
    // Ne PAS supprimer title et desc (accessibilité)
    {
      name: 'removeTitle',
      active: false,
    },
    {
      name: 'removeDesc',
      active: false,
    },
    {
      name: 'removeUselessDefs',
      active: true,
    },
    {
      name: 'removeEditorsNSData',
      active: true,
    },
    {
      name: 'removeEmptyAttrs',
      active: true,
    },
    {
      name: 'removeHiddenElems',
      active: false, // Garder les éléments avec aria-hidden pour accessibilité
    },
    {
      name: 'removeEmptyText',
      active: false, // Garder les textes vides qui peuvent être nécessaires
    },
    {
      name: 'removeEmptyContainers',
      active: true,
    },
    {
      name: 'removeViewBox',
      active: false, // Garder viewBox pour le responsive
    },
    {
      name: 'cleanupEnableBackground',
      active: true,
    },
    {
      name: 'minifyStyles',
      active: true,
    },
    {
      name: 'convertStyleToAttrs',
      active: true,
    },
    {
      name: 'convertColors',
      active: true,
    },
    {
      name: 'convertPathData',
      active: true,
    },
    {
      name: 'convertTransform',
      active: true,
    },
    {
      name: 'removeUnknownsAndDefaults',
      active: false, // Garder pour préserver les attributs ARIA
    },
    {
      name: 'removeNonInheritableGroupAttrs',
      active: true,
    },
    {
      name: 'removeUselessStrokeAndFill',
      active: false, // Garder pour préserver les styles
    },
    {
      name: 'removeUnusedNS',
      active: true,
    },
    {
      name: 'cleanupNumericValues',
      active: true,
    },
    {
      name: 'cleanupListOfValues',
      active: true,
    },
    {
      name: 'moveGroupAttrsToElems',
      active: true,
    },
    {
      name: 'collapseGroups',
      active: true,
    },
    {
      name: 'mergePaths',
      active: true,
    },
    {
      name: 'convertShapeToPath',
      active: true,
    },
    {
      name: 'sortAttrs',
      active: true,
    },
    {
      name: 'removeDimensions',
      active: false, // Garder width et height pour le responsive
    },
  ],
};

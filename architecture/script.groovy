import com.structurizr.model.*;
import com.structurizr.view.*;
// Hides elements that aren't connected by a relationship
for (View view : workspace.getViews().getViews()) {
    Set<RelationshipView> relationships = view.getRelationships();

    Set<String> elementIds = new HashSet<>();
    relationships.forEach(rv -> elementIds.add(rv.getRelationship().getSourceId()));
    relationships.forEach(rv -> elementIds.add(rv.getRelationship().getDestinationId()));

    for (ElementView elementView : view.getElements()) {
        if (elementView.getElement() instanceof DeploymentNode) {
        } else {
            if (!elementIds.contains(elementView.getId())) {
                view.removeElement(elementView.getElement());
            }
        }
    }
}
